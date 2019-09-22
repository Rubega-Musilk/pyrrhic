import hashlib
import binascii

from platform import uname
from .util import pascal_bytes
from typing import Callable, Iterable, List

_HASHER_IMPL = hashlib.sha256 # 256 bits
"""Implementation of a hash function with sufficient collision resistance
to make input collisions astronomically unlikely.

For buckwheat's use-case, this does not have to be cryptographically secure,
only well-distributed. e.g. if this becomes a bottleneck, try something like
xxHash.
"""

_HASHER_BITS = 256
_HASHER_BYTES = _HASHER_BITS // 8

BUFSIZE = (64 * 1024) # 64k


_SALT = str(tuple(uname())).encode("ascii")
"""Salt so that hashed functions are not easily portable from
machine-to-machine because their behaviour may be platform-dependent even
if their bytecode isn't.

This is meant to prevent user mistakes e.g. accidentally copying cached files,
not as a security feature."""


def _SALTED_HASHER():
    hasher = _HASHER_IMPL()
    hasher.update(_SALT)
    return hasher



def to_hex(hash_bytes: bytes) -> str:
    return binascii.hexlify(hash_bytes).decode("ascii")


def from_hex(hash_hex: str) -> bytes:
    return binascii.unhexlify(hash_hex)


def _transcribe_value(value: any) -> bytes:
    """Turns a Python value into an unambiguous byte representation"""
    return pascal_bytes(repr(value).encode("utf-8"))


def _transcribe_code(code) -> bytes:
    """Turns a python `something.__code__` object into a unique byte
    representation (like serialising, but we don't care about parsing the
    result back into a code object) for hashing. The important property for us
    is that the result is reproducible for the same code (i.e. don't pickle
    memory addresses)."""
    yield _transcribe_value("CODE")
    yield pascal_bytes(code.co_code)

    yield _transcribe_value("CELLS")
    yield _transcribe_value(len(code.co_cellvars))
    for i in code.co_cellvars:
        if type(i) == type(code):
            yield from _transcribe_code(i)
        else:
            yield _transcribe_value(i)

    yield _transcribe_value("CNST")
    yield _transcribe_value(len(code.co_consts))
    for i in code.co_consts:
        if type(i) == type(code):
            yield from _transcribe_code(i)
        else:
            yield _transcribe_value(i)

    yield _transcribe_value("FREE")
    yield _transcribe_value(len(code.co_freevars))
    for i in code.co_freevars:
        yield _transcribe_value(i)

    yield _transcribe_value("NAME")
    yield _transcribe_value(len(code.co_names))
    for i in code.co_names:
        yield _transcribe_value(i)

    yield _transcribe_value("VARN")
    yield _transcribe_value(len(code.co_varnames))
    for i in code.co_varnames:
        yield _transcribe_value(i)

    yield _transcribe_value("EDOC")


def _transcribe_function(cmd):
    """
    Turns a Python function into a unique byte representation (like
    serialising, but we don't care about parsing the result back into a
    function) for hashing. The important property for us is that the result
    is reproducible for the same code (i.e. don't pickle memory addresses).

    Note: This does not currently (and there are no plans to) support recursive
    functions (for solving this automatically, see [Automatically Serialising \
    Recursive Inner Functions in Python using the Y Combinator](https://medium\
    .com/@emlynoregan/automatically-serialising-recursive-inner-functions-in-\
    python-using-the-y-combinator-fc5d37e50b29) and bring your computer science
    degree!)
    """

    yield _transcribe_value("FUNC")
    if cmd.__defaults__:
        yield _transcribe_value("DFLT")
        yield _transcribe_value(len(cmd.__defaults__))
        yield [_transcribe_code(x) for x in cmd.__defaults__]

    if cmd.__kwdefaults__:
        yield _transcribe_value("KWDF")
        yield _transcribe_value(len(cmd.__kwdefaults__))
        yield [_transcribe_code(x) for x in cmd.__kwdefaults__]

    if cmd.__closure__:
        yield _transcribe_value("CLOS")
        yield _transcribe_value(len(cmd.__closure__))
        for j in cmd.__closure__:
            i = j.cell_contents
            if type(i) == type(cmd):
                yield from _transcribe_function(i)
            else:
                yield _transcribe_value(i)

    yield from _transcribe_code(cmd.__code__)
    yield _transcribe_value("CNUF")


def functions(fns: List[Callable]):
    """Returns a hash from the bytecode for a list of functions or methods."""
    hasher = _SALTED_HASHER()

    for fn in fns:

        # hash bytecode etc.
        for part in _transcribe_function(fn):
            hasher.update(part)

    return hasher.digest()


def function(fn: Callable):
    """Returns a hash from the bytecode for a function or method."""
    return functions([fn])


def strings(xs: Iterable[str]):
    """Hashes multiple strings at once."""
    hasher = _SALTED_HASHER()

    for x in xs:
        hasher.update(x.encode('utf-8'))

    return hasher.digest()


def at(path):
    """Returns a hash for a file at a given path."""

    hasher = _SALTED_HASHER()

    with open(str(path), 'rb') as fp:
        while True:
            data = fp.read(BUFSIZE)
            if not data:
                break
            hasher.update(data)

    return hasher.digest()
