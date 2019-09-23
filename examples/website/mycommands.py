import os
from datetime import datetime
import pyrrhic as pyr
from pathlib import Path
from lxml import etree as ET


def make_xml_index(dest):
    # Constructs a command function to generate an XML index of markdown pages

    # Get a pathlib Path
    p_dest = Path(dest)

    def get_markdown_info(path):
        # Read the first four lines of a markdown file to extract title and
        # first paragraph as a summary.
        # Title
        # ====
        #
        # Paragraph One
        parts = []
        with open(str(path), "rb") as fp:
            title = next(fp)
            _ = next(fp)
            _ = next(fp)
            for line in fp:
                if line.isspace(): break
                parts.append(line)
            return title.strip(), b" ".join(parts).strip()

    # Define a function that takes a sequence of inputs (basedir, filename)
    # and generates a 4-tuple per output (in our case, just one output):
    #   1. output path
    #   2. input files used as inputs
    #   3. input files read from, directly or indirectly
    #       (in our case (3) is the same as (2)
    #   4. a lazy function with no arguments that performs the work when
    #       called.
    # The purpose of this function is to describe all outputs, all dependencies
    # per output, and lazily implement how to generate each output.
    def fn(inputs: pyr.types.TCommandInputs) -> pyr.types.TCommandReturn:
        paths = [] # type: List[Path]

        for basedir, path in inputs:
            paths.append((Path(basedir), Path(path)))

        # Define our function that actually does the work
        # For this, we're generating XML that summarises a bunch of
        # markdown pages
        def work() -> bytes:
            root = ET.Element("pages")

            for basedir, input in sorted(paths, key=lambda x: str(x[1]), reverse=True):
                page = ET.Element("page")

                page_id = ET.Element("id")
                if str(input.parent) == '.':
                    page_id.text = input.stem
                else:
                    page_id.text = str(input.parent) + "/" + input.stem


                page_mod = ET.Element("modified")
                page_mod.text = str(datetime.fromtimestamp(os.path.getmtime(str(basedir/input))))

                title, summary = get_markdown_info(basedir/input)

                page_title = ET.Element("title")
                page_title.text = title

                page_summary = ET.Element("summary")
                page_summary.text = summary

                page.append(page_id)
                page.append(page_title)
                page.append(page_mod)
                page.append(page_summary)
                root.append(page)

            return ET.tostring(root, encoding='utf-8', pretty_print=True, xml_declaration=True)

        yield (p_dest, paths, paths, work)

    # Finally return these constructed functions
    return fn, "make_xml_index", pyr.hash.function(fn)



def make_html_pages(
        dest,
        index=None,
    ):
    # Constructs a command function to generate HTML pages for each input

    if not index: raise RuntimeError("Need pages_index kwarg")

    # Get pathlib Paths
    p_destdir = Path(dest)
    p_index = Path(index)

    # Define a function that takes a sequence of inputs (basedir, filename)
    # and generates a 4-tuple for each output
    #   1. output path
    #   2. input files used as inputs
    #   3. input files read from, directly or indirectly
    #   4. a lazy function with no arguments that performs the work when
    #       called.
    # The purpose of this function is to describe all outputs, all dependencies
    # per output, and lazily implement how to generate each output.
    def fn(inputs: pyr.types.TCommandInputs) -> pyr.types.TCommandReturn:
        for basedir, path in inputs:
            p_basedir, p_path = Path(basedir), Path(path)
            p_destfile = p_path.with_suffix(".html")

            yield (
                p_destdir / p_destfile,
                [(p_basedir,p_path)],
                [(p_basedir,p_path), (Path("."), p_index)],
                lambda: b"\n".join([pyr.util.read(p_basedir/p_path),
                                       pyr.util.read(p_index)])
            )

    # Finally return these constructed functions
    return fn, "make_html_pages", pyr.hash.function(fn)
