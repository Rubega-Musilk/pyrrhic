from typing import Callable, Iterator, List, Mapping, Optional, Set, Tuple
from pathlib import Path
from collections import OrderedDict

from itertools import chain
import fnmatch # for path-style globbing against a list of strings
import copy

from .types import TCommand, TRule, TRules
from .util import as_pathlib_path, dquo, str_encode, str_decode, do_not_call
from .hash import to_hex, from_hex
from .util import RecursionError as bwRecursionError

_p = as_pathlib_path

def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except FileNotFoundError:
        return -1.0


class Globber:
    """Enables globbing against both the file system and outputs generated
    by a rule, even if they haven't been written to disk yet (such as when
    generating the dependency graph).

    Members:
        outputs (Set[str]): set of outputs generated by rules so far"""

    def __init__(self) -> None:
        self.outputs = set() # type: Set[str]

    def glob(self, inputs: Iterator[Tuple[Path, Path]]) -> Iterator[Tuple[Path, Path]]:
        """Apply a glob to a set of input tuples `(base, path)`, expanding
        any glob patterns (e.g. `**/*.txt`) in each path element, and matching
        against both files on disk and outputs that are queued to be written
        (even if they haven't appeared on disk yet)."""
        seen = set() # type: Set[Path]
        path_type = None

        for base, path in inputs:
            if "*" not in str(path):
                yield base, path
            else:
                path_type = type(path)

                # glob against file system
                real_files = base.glob(str(path))

                # glob against existing targets
                target_files = fnmatch.filter(self.outputs, str(base / path))

                for match in chain(real_files, target_files):
                    if match not in seen:
                        seen.add(match)
                        yield (base, path_type(match).relative_to(base))


class Node:
    def __init__(self, path: Path) -> None:
        self.path = path        # type: Path
        self.links = set()      # type: Set[Link]
        self.dlinks = set()     # type: Set[Link] # links, direct only
        self.rlinks = set()     # type: Set[Link] # reverse links
        self.drlinks = set()    # type: Set[Link] # reverse links, direct only
        self.production = None  # type: Optional[Callable]
        self.index = 0          # type: int

    def __lt__(self, other) -> bool:
        return self.path < other.path

    def __eq__(self, other) -> bool:
        assert type(self) == type(other), (repr(self), repr(other))
        return self.path == other.path

    def apply(self):
        cmd, *_ = self.production
        sources = [(link.basedir, link.src.path.relative_to(link.basedir)) for link in self.drlinks]

        for dest, _, _, writer in cmd(sources):
            #assert self.path == dest, (self.path, dest)
            if self.path != dest:
                print("WARN: self.path != dest (%s, %s)" % (self.path, dest))


            # make parent dirs
            #for parent in reversed(self.path.parents):
            for parent in reversed(dest.parents):
                if not parent.is_dir():
                    try:
                        parent.mkdir()
                    except FileNotFoundError:
                        pass

            #with self.path.open("wb") as fp:
            with dest.open("wb") as fp:
                fp.write(writer())

        return

        with self.path.open("wb") as fp:
            fp.write(b"".join(cmd(sources)))

    def unlink(self):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __hash__(self):
        #return hash(tuple(self.path, tuple(sorted(self.links))))
        return hash(self.path)

    def __repr__(self):
        return "<Node: path=%s, productions: %s, dependencies: %s, direct-dependencies: %s>" % (repr(self.path), repr(self.links), repr(self.rlinks), repr(self.drlinks))


class Link:
    """Represents a directional (i.e.one-way) link to a [[Node|Nodes]] `source`
    -> `dest` created by a certain [[TCommand|command]. The source node is
    included so that questions can also be asked in reverse e.g. not only
    what nodes were created from the source, but what were all the dependencies
    of the destination."""
    # TODO TCommand isn't right?
    def __init__(self, cmd: TCommand, src: Node, dest: Node, basedir: Optional[Path] = None) -> None:
        if src == dest:
            raise bwRecursionError("Cycle detected: source and dest are the same (%s)" % repr((cmd[1], src)))

        (_, self.cmd_name, self.cmd_hash) = cmd
        self.src  = src  # type: Node
        self.dest = dest # type: Node

        # basedir is just used when finally applying a DAG
        if basedir is not None:
            self.basedir = basedir
        else:
            self.basedir = Path("")

    def __eq__(self, other: "Link") -> bool:
        # NOTE: while `cmd_name` doesn't change any behaviour, two functions
        # with the same implementation (and therefore same hash) could be used
        # with different names in different places. For this reason the
        # distinction is maintained in order to aid human debugging.
        assert type(self) == type(other)
        return \
            (self.cmd_name == other.cmd_name) and \
            (self.cmd_hash == other.cmd_hash) and \
            (self.src == other.src) and \
            (self.dest == other.dest)

    def __lt__(self, other):
        return \
            (self.cmd_name < other.cmd_name) or \
            (self.cmd_hash < other.cmd_hash) or \
            (self.src < other.src) or \
            (self.dest < other.dest)

    def __hash__(self):
        return hash(tuple([self.cmd_hash, self.cmd_name, self.src, self.dest]))

    def __repr__(self):
        return "<Link %s %s %s => %s>" % \
            (repr(self.cmd_name), to_hex(self.cmd_hash)[0:8], dquo(str(self.src.path)), dquo(str(self.dest.path)))


class DAG:
    """Dependency graph as a Directed Acyclic Graph"""
    def __init__(self):
        self.nodes = OrderedDict() # type: Mapping[str, Node]

    def get(self, node: Node) -> Node:
        """Return either a reference to an existing node equal to the `node`
        argument or, if one is not found in the DAG, adds the `node` argument
        to the DAG and returns it.
        """
        if not node.path in self.nodes:
            self.nodes[node.path] = node

        return self.nodes.get(node.path)

    def pick(self, path: Path) -> Optional[Node]:
        """Return the node for the given path if it exists in the DAG,
        otherwise returns None."""
        return self.nodes.get(path)

    def __repr__(self):
        return repr(self.nodes)

    def __eq__(self, other: "DAG") -> bool:
        sorted_nodes_a = OrderedDict(sorted(self.nodes.items()))
        sorted_nodes_b = OrderedDict(sorted(other.nodes.items()))
        return sorted_nodes_a == sorted_nodes_b

    def has_cycles(self) -> Optional[Tuple[Node, Link]]:
        """Detect if the DAG has a cycle.

        Returns:
            * If a cycle is detected, a 2-tuple of the first found
              node and link creating the cycle.
            * Otherwise, `None`.
        """

        # Algorithm from CLRS 3rd edition, 22.3 Depth-first search

        colors = dict() # type: Mapping[Path, int]

        # mapping from node.path to a color
        # white means "unseen", grey means discovered, black means finished
        _WHITE, _GREY, _BLACK = (0, 1, 2)

        def visit(node) -> Optional[Tuple[Node, Link]]:
            colors[node.path] = _GREY

            for link in node.links:
                if colors[link.dest.path] == _WHITE:
                    problem = visit(link.dest)
                    if problem: return problem
                elif colors[link.dest.path] == _GREY:
                    # Back-edge means cycle
                    return (node, link)

            colors[node.path] = _BLACK
            return None

        for node in self.nodes.values():
            colors[node.path] = _WHITE

        for node in self.nodes.values():
            if colors[node.path] == _WHITE:
                problem = visit(node)
                if problem: return problem
            else:
                assert colors[node.path] == _BLACK

        return None

    def source_nodes(self) -> Iterator[Node]:
        """Return all source nodes (nodes with no parent)."""
        for node in self.nodes.values():
            if not node.rlinks:
                yield node

    def _serialize(self) -> Iterator[str]:
        sorted_nodes = OrderedDict(sorted(self.nodes.items()))
        keys = list(sorted_nodes.keys())
        yield "# DAG serialised by Pyrrhic"
        yield "# See https://github.com/tawesoft/pyrrhic"
        yield "# See https://www.tawesoft.co.uk/products/open-source-software"
        yield "format 2"

        # define each node in an indexable order
        yield "\n# node num_links path"
        for node in sorted_nodes.values():
            yield "node %d %s" % (len(node.links), str_encode(str(node.path)))

        # define each unique command function in an indexable order
        seen_cmds = set() # type: Tuple[str, byte]
        cmds = list()
        for node in sorted_nodes.values():
            for link in sorted(list(node.links)):
                cmd_name, cmd_hash = link.cmd_name, link.cmd_hash
                if (cmd_name, cmd_hash) not in seen_cmds:
                    seen_cmds.add((cmd_name, cmd_hash))
                    cmds.append((cmd_name, cmd_hash))

        yield "\n# func name hash"
        for cmd_name, cmd_hash in cmds:
            yield "func %s %s" % (cmd_name, to_hex(cmd_hash))

        yield "\n# (d)link source_node_index dest_node_index function_index"
        yield "# dlink means the input is direct, link means indirect"
        for index, node in enumerate(sorted_nodes.values()):
            for link in sorted(list(node.links)):
                if link in node.dlinks:
                    yield "dlink %d %d %d" % (index, keys.index(link.dest.path), cmds.index((link.cmd_name, link.cmd_hash)))
                else:
                    yield "link %d %d %d" % (index, keys.index(link.dest.path), cmds.index((link.cmd_name, link.cmd_hash)))


    def serialize(self) -> str:
        """Serialise the digraph to a string for persisting to disk"""
        return "\n".join(self._serialize())

    @classmethod
    def deserialize(self, data: str) -> 'DAG':
        dag = DAG()
        paths = list()  # type: List[str]
        commands = list() # type: List[Tuple[str, bytes]]

        for lineno, line in enumerate(data.split("\n")):

            # ignore whitespace or comments
            if line == "" or line.isspace() or line.startswith("#"):
                continue

            parts = line.split(" ", maxsplit=1)
            if len(parts) != 2: raise SyntaxError(lineno)

            label, rest = parts

            if label == "format":
                if int(rest) != 2:
                    # unrecognised future format
                    # return empty DAG for compatibility
                    print("INFO: pyrrhic.rules.DAG.deserialize: skipping DAG with unknown format")
                    return DAG()

            elif label == "node":
                parts = rest.split(" ", maxsplit=2)
                if len(parts) != 2: raise SyntaxError(lineno)
                _, path = parts

                path = Path(str_decode(path))
                dag.get(Node(path))
                paths.append(path)

            elif label == "func":
                parts = rest.split(" ", maxsplit=2)
                if len(parts) != 2: raise SyntaxError(lineno)
                cmd_name, cmd_hash = parts
                bin_hash = from_hex(cmd_hash)
                commands.append((cmd_name, bin_hash))

            elif label == "link":
                parts = rest.split(" ", maxsplit=2)
                src, dest, cmd_index = parts
                if len(parts) != 3: raise SyntaxError(lineno)

                src_node = dag.nodes.get(paths[int(src)])
                dest_node = dag.nodes.get(paths[int(dest)])
                cmd = commands[int(cmd_index)]
                cmd_name, cmd_hash = cmd
                cmd = (do_not_call, cmd_name, cmd_hash)
                src_node.links.add(Link(cmd, src_node, dest_node))
                dest_node.rlinks.add(Link(cmd, src_node, dest_node))

            elif label == "dlink":
                parts = rest.split(" ", maxsplit=2)
                src, dest, cmd_index = parts
                if len(parts) != 3: raise SyntaxError(lineno)

                src_node = dag.nodes.get(paths[int(src)])
                dest_node = dag.nodes.get(paths[int(dest)])
                cmd = commands[int(cmd_index)]
                cmd_name, cmd_hash = cmd
                cmd = (do_not_call, cmd_name, cmd_hash)
                src_node.links.add(Link(cmd, src_node, dest_node))
                dest_node.rlinks.add(Link(cmd, src_node, dest_node))
                src_node.dlinks.add(Link(cmd, src_node, dest_node))
                dest_node.drlinks.add(Link(cmd, src_node, dest_node))

            else:
                raise SyntaxError("Unknown command %s on line %d" % (label, lineno))

        return dag

    def _digraph(self, name) -> Iterator[str]:
        sorted_nodes = OrderedDict(sorted(self.nodes.items()))
        keys = list(sorted_nodes.keys())

        yield "digraph \"%s\" {" % name
        yield "    rankdir=LR"

        # enumerate the nodes with labels
        for index, node in enumerate(sorted_nodes.values()):
            yield "    N_%d [label=%s];" % (index, dquo(str(node.path)))

        # specify the links from each node
        for index, node in enumerate(sorted_nodes.values()):
            yield "\n    // Source %s" % (dquo(str(node.path)))
            for link in node.links:
                # brackets mean its an indirect link e.g. is an implicit input
                # e.g. an @import or #include
                l,r = "(", ")"
                if link in node.dlinks: l,r="",""
                yield "    N_%d -> N_%d [label=%s];" % \
                    (index, keys.index(link.dest.path), dquo(l+link.cmd_name+r))

        yield "}"

    def pydot(self, title: str):
        import pydot
        graph, = pydot.graph_from_dot_data(self.digraph(title))
        return graph

    def digraph(self, name: str) -> str:
        """
        Encode the graph in DOT (graph description language).

        Usage:
            Pipe the result to `display`, `dot | display`,
            or `dot -Tpng > out.png`
        """
        return "\n".join(self._digraph(name))

    def apply(self,
        previous_dependency_graph: Optional["DAG"],
        _mtimes: Optional[Mapping[str, float]] = None
    ) -> Iterator[Tuple[str, Node]]:
        return sorted(list(self._apply(previous_dependency_graph, _mtimes)), key=lambda x: x[1].index)

    def _apply(self,
        previous_dependency_graph: Optional["DAG"],
        _mtimes: Optional[Mapping[str, float]] = None
    ) -> Iterator[Tuple[str, Node]]:
        """Apply a set of rules to create outputs.

        Arguments:
            previous_dependency_graph: a previous dependency graph of a set of rules
                (if one exists) so that old targets can be removed, or `None`.
            _mtimes: for testing, a cache of file-last-modified times.

        Return value:
            A sequence of 2-tuples representing the result of comparing the DAGs.

            Each 2-tuple contains:
                1. Either the string "w" (write) or the string "d" (delete)
                2. An object. If the first item in the tuple is "w", call the
                    `apply()` method on the object to evaluate side-effects, e.g.
                    write output. If the first item in the tuple is "d", call the
                    `unlink()` method on the object to delete it.
        """

        if previous_dependency_graph is None:
            previous_dependency_graph = DAG()

        cdag = self # type: DAG # current DAG
        pdag = previous_dependency_graph # type: DAG # previous DAG

        # Cache for last-modified times
        if _mtimes is None:
            mtimes = dict() # type: Mapping[str, float]
        else:
            mtimes = copy.copy(_mtimes)

        def _getmtime(path):
            spath = str(path)
            mt = mtimes.get(spath, None)
            if mt is None:
                mt = _mtime(path)
                mtimes[spath] = mt
            return mt

        seen = set() # type: Set[Node]

        def _visit(node: Node):
            # mark node and all productions
            if node not in seen:
                yield ("w", node)
            seen.add(node)
            for child in sorted([x.dest for x in node.links]):
                yield from _visit(child)

        def search(node):

            for dest in sorted([x.dest for x in node.links]):
                pnode = pdag.pick(dest.path)

                if pnode in seen:
                    continue

                elif pnode is None:
                    # the dest doesn't exist in the pdag:
                    yield from _visit(dest)
                    continue

                elif dest.links != pnode.links or dest.rlinks != pnode.rlinks:
                    # the dest is generated by different rules
                    yield from _visit(dest)
                    continue

                else:
                    # the source is newer than its outputs?
                    mtime_src = _getmtime(node.path)
                    mtime_dest = _getmtime(dest.path)

                    if mtime_src < 0:
                        raise FileNotFoundError("input %s not found" % repr(str(node.path)))

                    if (mtime_dest < 0) or (mtime_src > mtime_dest):
                        yield from _visit(dest)
                        mtimes[str(dest.path)] = mtime_src
                        continue

                yield from search(dest)


        # identify removed nodes
        for _, node in sorted(list(pdag.nodes.items())):

            # ignore source nodes
            if not node.rlinks: continue

            # ignore nodes also present in cdag
            if node.path in cdag.nodes: continue

            yield("d", node)
            mtimes[str(node.path)] = -1.0


        for node in cdag.source_nodes():
            yield from search(node)


def resolve(rules: TRules) -> Iterator[Tuple[TCommand, Path, List[Tuple[Path, Path]]]]:
    """
    Evaluate each rule to generate path information (only) without yet
    executing the lazy callback that generates output.
    """
    globber = Globber()

    for rule in rules:
        cmd, inputs = rule
        fn, *_ = cmd

        outputs = fn(globber.glob([(_p(base), _p(path)) for base, path in inputs]))

        for output, inputs, sources, _writer in outputs:
            globber.outputs.add(str(output))
            yield cmd, _p(output), set([(_p(b), _p(p)) for b, p in inputs]), set([(_p(b), _p(p)) for b, p in sources])


def to_dag(rules: TRules) -> DAG:
    """Build a dependency graph from a list of rules."""
    dag = DAG()
    i = 0

    # Build DAG
    for cmd, dest, inputs, sources in resolve(rules):
        dest_node = dag.get(Node(dest))
        if dest_node.production is not None:
            raise RuntimeError("Output %s used in multiple productions" % repr(dest))
        dest_node.production = cmd

        for basedir, source in sources:
            src_node = dag.get(Node(basedir / source))
            src_node.links.add(Link(cmd, src_node, dest_node))
            dest_node.rlinks.add(Link(cmd, src_node, dest_node, basedir=basedir))

        for (basedir, source) in inputs:
            src_node = dag.get(Node(basedir / source))
            src_node.links.add(Link(cmd, src_node, dest_node))
            dest_node.rlinks.add(Link(cmd, src_node, dest_node, basedir=basedir))
            src_node.dlinks.add(Link(cmd, src_node, dest_node))
            dest_node.drlinks.add(Link(cmd, src_node, dest_node, basedir=basedir))

        dest_node.index = i # for ordering
        i+=1

    # Check for cycles
    result = dag.has_cycles()
    if result is not None:
        raise bwRecursionError("Cycle detected in dependency graph at %s" % repr(result))

    return dag


def deserialize(s: str):
    return DAG.deserialize(s)
