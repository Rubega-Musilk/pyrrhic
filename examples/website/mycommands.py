import os
import html
from datetime import datetime, date
import pyrrhic as pyr
from pathlib import Path
from lxml import etree as ET


def get_markdown_info(path, rest=False, encoding="utf-8"):
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
        if not rest:
            return title.strip(), b" ".join(parts).strip()
        else:
            import mistune
            return title.strip(), b" ".join(parts).strip(), mistune.markdown(b"".join(fp).decode(encoding))


def make_xml_index(dest):
    # Constructs a command function to generate an XML index of markdown pages

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

        # Get a pathlib Path
        p_dest = Path(dest)
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


def mk_nav(pages, root):
    yield """<li><a href="%s">Home</a></li>""" % root
    for page in sorted(pages, key=lambda x: x.find("id").text):
        title = page.find('title').text
        id = page.find('id').text
        yield """<li><a href="%s%s.html">%s</a></li>""" % (root, id, title)


def make_html_pages(
        dest,
        template=None,
        pages_index=None,
        encoding: str = "utf-8",
    ):
    # Constructs a command function to generate HTML pages for each input
    # Use the pages_index and posts_index XML to generate navigation

    if not template: raise RuntimeError("Need template kwargs")
    if not pages_index: raise RuntimeError("Need pages_index kwarg")

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

        # Get pathlib Paths
        p_destdir = Path(dest)
        p_template = Path(template)
        p_pages_index = Path(pages_index)

        def parse_markdown(path):
            title, desc, rest = get_markdown_info(path, True, encoding)
            return title.decode(encoding), desc.decode(encoding), rest

        def work(basedir, path) -> bytes:
            pages = ET.fromstring(pyr.util.read(p_pages_index))
            template = pyr.util.read(p_template)
            root = "../" * str(path).count("/")
            title, desc, body = parse_markdown(basedir / path)
            return template.decode(encoding).format(
                title=title,
                desc=desc,
                page_nav="\n".join(mk_nav(pages, root)),
                body=body,
                root=root,
            ).encode(encoding)

        for basedir, path in inputs:
            p_basedir, p_path = Path(basedir), Path(path)
            p_destfile = p_path.with_suffix(".html")

            yield (
                p_destdir / p_destfile,
                [(p_basedir,p_path)],
                [(p_basedir,p_path),
                    (Path("."), p_pages_index),
                    (Path("."), p_template)],
                lambda: work(p_basedir, p_path)
            )

    # Finally return these constructed functions
    return fn, "make_html_pages", pyr.hash.function(fn)


def make_html_indexes(
        dest,
        template=None,
        pages_index=None,
        posts_index=None,
        src_dir=None,
        encoding: str = "utf-8",
        posts_per_page: int = 3
    ):
    # Constructs a command function to generate HTML pages for each input
    # Use the pages_index and posts_index XML to generate navigation

    if not template: raise RuntimeError("Need template kwargs")
    if not pages_index: raise RuntimeError("Need pages_index kwarg")
    if not posts_index: raise RuntimeError("Need posts_index kwarg")
    if not src_dir: raise RuntimeError("Need src_dir kwarg")


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

        # Get pathlib Paths
        p_destdir = Path(dest)
        p_template = Path(template)
        p_pages_index = Path(pages_index)
        p_posts_index = Path(posts_index)

        p_src_dir = Path(src_dir)

        def summary(post, root):
            title = post.find("title").text
            url = post.find("id").text + ".html"

            created = post.find("id").text
            created = created.split("-", maxsplit=1)[0]
            _, y, md = created.split("/")
            m = md[0:2]
            d = md[2:4]
            created = date(year=int(y), month=int(m), day=int(d)).strftime("%A %d %B %Y")

            modified = post.find("modified").text
            summary = post.find("summary").text
            return """
<h2><a href="%s%s">%s</a></h2>
<p><i>%s</i></p>
<p>%s</p>
""" % (root, url, title, created, summary)

        def work(index: int, posts, last: bool) -> bytes:
            pages = ET.fromstring(pyr.util.read(p_pages_index))

            template = pyr.util.read(p_template)
            root = ""
            title, desc = "Latest Posts", "Latest posts for my website"
            if index > 0:
                title += " (Page %d)" % (index+1)
                root = "../"
            body = "\n".join([summary(x, root) for x in posts])
            if not last:
                body += """<div><a href="%sarchive/%d.html" class="button">Previous Items</a></p>""" % (root, index+2)
            return template.decode(encoding).format(
                title=title,
                desc=desc,
                page_nav="\n".join(mk_nav(pages, root)),
                body=body,
                root=root,
            ).encode(encoding)

        def chunks(l, n):
            """Yield successive n-sized chunks from l."""
            # https://stackoverflow.com/a/312464/5654201
            for i in range(0, len(l), n):
                yield l[i:i + n]

        if p_posts_index.exists():
            posts = list(ET.fromstring(pyr.util.read(p_posts_index)))
        else:
            raise pyr.util.Redo

        for item, last in pyr.util.list_lastitems(enumerate(chunks(posts, posts_per_page))):
            index, chunk = item

            if index == 0:
                p_destfile = Path("index.html")
            else:
                p_destfile = Path("archive/%d.html" % (index+1))

            pages = [(Path(p_destdir), Path(x.find('id').text+".html")) for x in chunk]

            yield (
                p_destdir / p_destfile,
                [],
                pages + [
                    (Path("."), p_posts_index),
                    (Path("."), p_pages_index),
                    (Path("."), p_template)
                ],
                lambda: work(index, chunk, last)
            )

    # Finally return these constructed functions
    return fn, "make_html_indexes", pyr.hash.function(fn)
