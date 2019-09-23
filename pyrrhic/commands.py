from typing import Callable, Optional, List, Mapping
from pathlib import Path
import os
from .types import TCommand, TCommandInputs, TCommandReturn, TPathLike, TScanner
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
    name: str = "cat",
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

    This is a building block usually used by other commands.
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
    name: str = "copy",
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


def compile_file(
    dest: str,
    compile_fn: Callable[[Path, Path], bytes],
    scan_fn: TScanner,
    name: str = "compile_file"
) -> TCommand:
    """
    Constructs a command that compiles a file, tracking its imports as
    dependencies.

    Arguments:
        dest: filename of compiled CSS to be written
        compile_fn: function that compiles a file to bytes, taking two arguments:
            1. Base directory
            2. Path relative to base directory
        scan_fn: function that parses a file's inputs (see `types.TScanner`)
        kwargs: list of arguments to pass to the sass.compile function

    Returns:
        A new [[TCommand]] function with a bound `dest` that implements this
        operation.

    This is a building block usually used by other commands.
    """

    p_dest = as_pathlib_path(dest)

    def read_fn(inputs: TCommandInputs) -> TCommandReturn:

        l_inputs = list(inputs)
        if len(l_inputs) != 1:
            raise RuntimeError("This command takes only one input")

        basedir, path = l_inputs[0]
        output = p_dest
        deps = [(basedir, path)] + list(scan_fn(basedir, path))

        yield (output, l_inputs, list(deps), lambda: compile_fn(basedir, path))

    return _mkret(read_fn, name)


def scss(dest: str, encoding: str="utf-8", name: str = "scss", **kwargs) -> TCommand:
    """
    Constructs a command that compiles a SCSS file, tracking its imports as
    dependencies. Use `kwargs` to pass additional arguments to the
    `sass.compile` function.
    """
    import sass  # pip install libsass

    def compile_fn(basedir, path):
        return sass.compile(filename=str(basedir/path), include_paths=[str(basedir)], **kwargs).encode(encoding)

    def scan_fn(basedir, path):
        return scanners.scss(basedir, path, encoding=encoding)

    return compile_file(dest, compile_fn, scan_fn, name)
