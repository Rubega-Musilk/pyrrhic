import pathlib
from typing import Callable, Iterable, Iterator, List, Optional, Tuple, Union

TMaybePath = Optional[pathlib.Path]
"""A type that represents either a `Path` object or a `None` value."""


TPathLike = Union[pathlib.Path, bytes, str]
"""A type representing either an instance of a `Path` or a string or
`bytes` object representing a path."""


TCommandInputs = Iterable[Tuple[TMaybePath, TMaybePath]]
"""An iterable of 2-tuples specifying a working directory and a path or pattern:

    1. the path of the base directory where an input file(s) is to be read
       from, using the base directory as a working directory
    2. and a path that represents ether:
        * one input file relative to the base directory e.g. `foo/bar.txt`
        * a glob-style pattern relative to the base directory specifying
          multiple input files from the file system and/or outputs of previous
          commands (even if those outputs have yet to be written to disk) e.g.
          `"foo/*.txt"`.
"""


TCommandReturn = Iterable[Tuple[pathlib.Path, List[Tuple[pathlib.Path, pathlib.Path]], List[Tuple[pathlib.Path, pathlib.Path]], Callable[[], bytes]]]
"""The return type of a command operation: a generator of 3-tuples containing:

    1. the path of an output file to be created by the command
    2. a list of all direct inputs of the output as a 2-tuple of:
        1. Base directory
        2. Path relative to base directory
    3. a list of all files read, including indirectly, to create the output as a 2-tuple of:
        1. Base directory
        2. Path relative to base directory
    3. lazy callable with no arguments that returns a [[bytes]] object
       that implements the writing of the output

The callable may not be called (e.g. it is not called when generating
a dependency graph), so as far as possible delay any intensive work to the
lazy callable and avoid any writes outside of the lazy callable."""


TCommand = Callable[[TCommandInputs], Tuple[Callable[[TCommandInputs], TCommandReturn], str, bytes]]
"""The type of a command function: a higher-order function that returns a
    3-tuple representation representing an operation.
    
    1. a callable `[[TCommandInputs]] -> [[TCommandReturn]]` that takes a
       sequence of inputs and generates a sequence of outputs
    2. a human-readable name of the callable
    3. a stable hash of the callable and its closure for persisting,
        indexing, detecting source code implementation changes, etc.
"""


TRule = Tuple[TCommand, TCommandInputs]
"""The type of a rule: a 2-tuple of a [[TCommand|command]] to be applied
(possibly lazily) to some [[TCommandInputs|inputs]] in order to build a plan
and incrementally (re)generate outputs when inputs update."""


TRules = List[TRule]
"""A list of objects of type [[TRule]]."""


TScanner = Callable[[pathlib.Path, pathlib.Path], Iterator[Tuple[pathlib.Path, pathlib.Path]]]
"""The type of a scanner function, a function that takes a 2-tuple of an input
file:

    1. Base directory
    2. Path relative to base directory

And generates a sequence of 2-tuples representing files included/imported by
the input file, and recursively files included/imported by imported files:

    1. Base directory
    2. Path relative to base directory
"""
