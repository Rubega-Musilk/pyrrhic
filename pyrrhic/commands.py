from typing import Callable, Optional, List
from pathlib import Path
import os
from .types import TCommand, TCommandInputs, TCommandReturn, TPathLike
from .util import identity, read, readall, as_pathlib_path
from .hash import function as hash_function
from . import scanners


def _mkret(fn: Callable, name: Optional[str]):
    """Helper function to turn (fn, name) => (fn, name, hash(fn))"""

    if not name:
        name = str(fn.__name__)

    return fn, name, hash_function(fn)


def cat(
    dest: TPathLike,
    name: str = "",
    trans: Optional[Callable[[bytes], bytes]] = None,
    trans_final: Optional[Callable[[bytes], bytes]] = None,
) -> TCommand:
    """
    Constructs a command that concatenates a sequence of inputs to a single
    output.

    Arguments:
        dest: path where the output is to be written
        name: an optional human-readable name for the function
        trans: a function `bytes` -> `bytes` applied to each input when it is
            read
        trans_final: a function `bytes` -> `bytes` applied to the whole
            input after it has been concatenated

    Returns:
        A new [[TCommand]] function with a bound `dest` that implements this
        operation.
    """
    if trans is None: trans = identity
    if trans_final is None: trans_final = identity

    p_dest = as_pathlib_path(dest)

    def cat_fn(inputs: TCommandInputs) -> TCommandReturn:
        paths = [] # type: List[Path]

        for basedir, path in inputs:
            paths.append((basedir, path))

        yield (p_dest, paths, paths,
            lambda: trans_final(b"".join(readall([b/p for b,p in paths], trans=trans))))

    return _mkret(cat_fn, name)


def copy(
    dest_dir: TPathLike,
    name: str = "",
    trans: Optional[Callable[[bytes], bytes]] = None
) -> TCommand:
    """
    Constructs a command that copies a sequence of inputs to a corresponding
    relative destination in a single output directory.

    Arguments:
        dest_dir: path to a directory where input is to be copied to
        name: an optional human-readable name for the function
        trans: a function `bytes` -> `bytes` applied to each input when it is
            read

    Returns:
        A new [[TCommand]] function with a bound `dest` that implements this
        operation.
    """

    if trans is None: trans = identity
    p_dest = as_pathlib_path(dest_dir)

    def cpy_fn(inputs: TCommandInputs) -> TCommandReturn:

        for basedir, path in inputs:
            output = p_dest / path
            input = basedir / path

            yield (output, [(basedir, path)], [(basedir, path)], lambda: trans(read(input)))

    return _mkret(cpy_fn, name)


def scss(dest: str, **kwargs) -> TCommand:
    """
    Constructs a command that compiles a Sass file, tracking its imports.

    Arguments:
        dest: filename of compiled CSS to be written
        kwargs: list of arguments to pass to the sass.compile function
    """

    p_dest = as_pathlib_path(dest)

    def compile_fn(basedir, path):
        import sass # pip install libsass
        return sass.compile(filename=str(basedir/path), include_paths=[str(basedir)], **kwargs).encode("utf-8")

    def read_fn(inputs: TCommandInputs) -> TCommandReturn:

        l_inputs = list(inputs)
        if len(l_inputs) != 1:
            raise RuntimeError("This command takes only one input")

        basedir, path = l_inputs[0]
        output = p_dest
        deps = [(basedir, path)] + list(scanners.scss(basedir, path))

        yield (output, l_inputs, list(deps), lambda: compile_fn(basedir, path))

    return _mkret(read_fn, "scss")
