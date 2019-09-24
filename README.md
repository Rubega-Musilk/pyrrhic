Pyrrhic
=======

Pyrrhic is a programmable Python build system that supports incremental
compilation, dynamic dependencies, and builtins for a range of tasks.

Pyrrhic is great for building static websites, or any build process where
tasks are written in Python.

![Dependency Graph](examples/website/dag-example.png)

*Image: Example of a Pyrrhic dependency graph for compiling SCSS files. The
brackets denote that an input was used in the command as an implicitly tracked
`@import`. The only explicit input was `main.scss`*


Features
--------

### Programmable

* Describe or generate your build rules in Python

* Implement your build steps as Python functions

### Dynamic dependencies

* Pyrrhic can automatically detect additional file dependencies without you
having to name them explicitly, e.g. by scanning files for `@import` statements

* Pyrrhic doesn't just track files: it also tracks the Python bytecode of the
command used to create an output. Change how a build command is implemented
and Pyrrhic knows to update the target.

### Correct and minimal

Save time on each build:

* Pyrrhic keeps the system up to date (correct) with the minimum of work.
  It will always apply the smallest necessary subtree of a dependency graph.

* Pyrrhic will delete stale outputs.

* If nothing changes, then Pyrrhic does nothing!

### Extensible

* Quickly create new commands out of the existing building blocks.

* Create new scanners to automatically pick up dependencies.

### Handy builtins

* `pyrrhic.commands.cat`: concatenate files with optional transformations (e.g. minify)
* `pyrrhic.commands.copy`: copy files with optional transformations
* `pyrrhic.commands.compile_file`: generic command to compile a file and track dependencies
* `pyrrhic.commands.scss`: compile SCSS⮕CSS (`pip install libsass`)
* More planned - please open pull requests if you implement one that works well for you

### Free and Open Source Software

See [COPYING.md](COPYING.md)


Usage
-----

You can get Pyrrhic and optional dependencies with e.g. `pip install lxml libsass mistune pyrrhic parsley pydot`

The folder `examples/website` uses Pyrrhic to build a full static website from
markdown files.

Here's what it's `build.py` looks like (open the original file for expanded
comments on how to use Pyrrhic):

```python
import pyrrhic
import mycommands

rules = [
    # Compile Sass SCSS files
    (pyrrhic.commands.scss('out/style.css'), [('styles', 'main.scss')]),

    # Make XML indexes for posts and pages
    (mycommands.make_xml_index("out/posts.xml"), [('content', 'posts/**/*.md')]),
    (mycommands.make_xml_index("out/pages.xml"), [('content', 'pages/*.md'), ('content', 'pages/**/*.md')]),

    # Makes HTML pages for each post and page
    (mycommands.make_html_pages("out", template="template.html", pages_index="out/pages.xml"),
        [('content', 'posts/**/*.md')]),
    (mycommands.make_html_pages("out", template="template.html", pages_index="out/pages.xml"),
        [('content', 'pages/*.md'), ('content', 'pages/**/*.md')]),

    # Makes index.html, archive/2.html, archive/3.html, etc.
    (mycommands.make_html_indexes("out", template="template.html", pages_index="out/pages.xml"),
        [('content', 'posts/**/*.md')]),
]

dag = pyrrhic.rules.to_dag(rules)
dag.pydot("Dependency Graph").write_png("dag.png") # optionally draw the graph

# Read the result of last-run
try:
    with Path("lastrun.pyrrhic.txt").open("r") as fp:
        prev = pyrrhic.rules.deserialize(fp.read())
except FileNotFoundError:
    prev = None

# Perform the build. The actual operations are lazy and don't get applied until
# the next step.
updates = dag.apply(prev)

# Here's a simple way to ask the user a question on the command-line:
def yes_or_no(q: str):
    while True:
        reply = str(input(q+' (y/n)? ')).lower().strip()
        if reply[0] == 'y':
            return True

for op, node in updates:
    # Each update is returned as a 2-tuple. The first argument is either "d"
    # for delete, or "w" for (over)write. This way you can interactively prompt
    # the user to delete or overwrite first if you want to.

    print("%s %s" % (op, node.path))
    if op == "d":
        if yes_or_no("Delete %s" % node.path):
            node.unlink()
    elif op == "w":
        node.apply()


# Save the build result so we don't have to do as much work next run!
with Path("lastrun.pyrrhic.txt").open("w") as fp:
    fp.write(dag.serialize())
```

Status
------

This was an internal tool that we've recently open-sourced. There might be
a few changes to be made based on community feedback.

The source files and examples contain lots of explanatory comments. But
there's no formal documentation and only partial `pytest` coverage.

Hopefully, you find Pyrrhic useful. Please let us know how it works out for
you! You can open a GitHub issue or feedback at
[open-source@tawesoft.co.uk](mailto:open-source@tawesoft.co.uk)

Our next planned feature is supporting parallel builds.


Support
-------

Pyrrhic should work with Python 3.4 or above (yes, 3.4! Our policy is to support
Debian "oldoldstable" until end of life).

For community support, please open a GitHub issue with code samples if you are
having any problems.

[Tawesoft Ltd](https://www.tawesoft.co.uk/) also offer paid commercial support
where we can sign NDAs, implement custom features, etc.



