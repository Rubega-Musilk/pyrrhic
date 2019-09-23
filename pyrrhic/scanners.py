from typing import Iterator, Tuple
from pathlib import Path
from .util import as_pathlib_path, read
import parsley


def scss(basedir, input, encoding="utf-8") -> Iterator[Tuple[Path, Path]]:
    """Scans a SCSS input file and its imports for `@import` statements"""

    p_basedir = as_pathlib_path(basedir)
    p_input = as_pathlib_path(input)
    contents = read(p_basedir / p_input).decode(encoding)
    parts = contents.split(";")
    imports = []

    def capture(arg):
        imports.append(arg)

    grammar = parsley.makeGrammar("""
        string      = ('"' <(~'"' anything)*>:val '"') -> capture(val)
                    | ("'" <(~"'" anything)*>:val "'") -> capture(val)
        imports     = string:first (ws ',' ws string)*
        import_rule = ws '@' 'i' 'm' 'p' 'o' 'r' 't' ws imports
    """, {'capture': capture})

    for part in parts:
        part = part.strip()
        # any "@import "foo"[, "bar", ...]"
        if not part.startswith("@import"): continue
        grammar(part).import_rule()

    for i in imports:
        p = Path(i+".scss")
        yield p_basedir, p
        yield from scss(p_basedir, p)
