import itertools
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterable, Iterator, List, Mapping, Optional, Tuple, TypeVar
from .types import TPathLike
import sys
import struct
import json


try:
    RecursionError = RecursionError
except NameError:
    class RecursionError(RuntimeError):
        pass



T = TypeVar('T')
"""Generic type"""

U = TypeVar('U')
"""Generic type"""


def do_not_call(*args, **kwargs) -> any:
    raise RuntimeError


def identity(x: T) -> T:
    return x


def read(path: TPathLike) -> bytes:
    with as_pathlib_path(path).open("rb") as fp:
        return fp.read()


def readall(paths: List[TPathLike], trans: Optional[Callable[[bytes], bytes]]) -> bytes:

    if trans is None:
        trans = identity()

    for path in paths:
        yield trans(read(path))


def as_pathlib_path(p: TPathLike) -> Path:
    """Given a [[TPathLike]] object, return a [[Path]] object."""
    if isinstance(p, Path):
        return p
    else:
        return Path(p)


@contextmanager
def cd(d):
    """Context-managed change directory e.g. `with cd(some_dir):`"""
    # https://stackoverflow.com/a/24176022/5654201
    prev = os.getcwd()
    os.chdir(os.path.expanduser(d))
    try:
        yield
    finally:
        os.chdir(prev)


def module_name_from_path(x: TPathLike) -> str:
    y = str(x)
    y = str(os.path.splitext(y)[0])
    y = y.replace("/", ".")
    y = y.replace("\\", ".")
    return y


def str_encode(x: str) -> str:
    """Encodes a Unicode string into an ascii-safe string"""
    return x.encode("unicode_escape").decode("utf-8")

def str_decode(x: str) -> str:
    """Decodes Unicode encoded as ascii-safe back into a string"""
    return x.encode("utf-8").decode("unicode_escape")

def dquo(x: str, ensure_ascii=True) -> str:
    """Like `repr` but always uses double quotes.
    e.g. `dquo("hello")` -> `"\"hello\""` """
    assert isinstance(x, str)
    return json.dumps(x, ensure_ascii=ensure_ascii, check_circular=False)
format_string_literal = dquo


def pairwise(iterable: Iterable) -> Iterable:
    """s -> (s0,s1), (s1,s2), (s2, s3), ..., (s_(n-1), None)"""
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.zip_longest(a, b, fillvalue=None)


def lpad(list: List, length: int, fillvalue: any = None) -> Iterable:
    """lpad([1,2,3], 5, 0) -> [0, 0, 1, 2, 3]"""
    times = length - len(list)
    if times < 1: return iter(list)
    padding = itertools.repeat(fillvalue, times)
    return itertools.chain(padding, list)


def rpad(iterable: Iterable, length: int, fillvalue: any = None) -> Iterable:
    """([1,2,3], 5, 0) -> [1, 2, 3, 0, 0]"""
    it = iter(iterable)
    while length > 0:
        try:
            yield next(it)
        except StopIteration:
            while length > 0:
                yield fillvalue
                length -= 1
        length -= 1


def cmp_mtime(a, b):
    """Compare two `mtime` values (e.g. for sorting)"""
    digits = sys.float_info.dig
    a = round(a, digits)
    b = round(b, digits)
    return b - a


def pascal_bytes(x: bytes) -> bytes:
    """Prefix a bytestring with its length (Pascal style)"""
    return struct.pack("<I", len(x)) + x


def dict_lastitems(xs: Mapping[T, U]) -> Iterator[Tuple[T, U, bool]]:
    """Iterates through a dict, generating a 3-tuple: `(key, value, last: bool)`
    where `last` is True iff it is the last item in the dict iterator.

    e.g. `xs -> (k0, v0, False), (k1, v1, False), ..., (kLast, vLast, True)`"""
    keys = pairwise(xs.keys())
    for key, key2 in keys:
        yield key, xs[key], key2 is None


def list_lastitems(xs: Iterator[T]) -> Iterator[Tuple[T, bool]]:
    """Iterates through a list, generating a 2-tuple: `(item, last: bool)`
    where `last` is True iff it is the last item in the list iterator.

    e.g. `xs -> (x0, False), (x1, False), ..., (xLast, True)`"""
    for x, y in pairwise(xs):
        yield x, y is None
