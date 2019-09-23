import pyrrhic as pyr
import importlib.machinery
from pathlib import Path

mycommands = importlib.machinery.SourceFileLoader('mycommands','./mycommands.py').load_module()

# Example build script for a simple static website.

# Usage: simply run as-is e.g. `python3 ./build.py` from the same directory.

# Our build script is a list of rules:
rules = [

    # Each rule takes the form of a 2-tuple (command, inputs).

    # A command is usually implemented by a higher-order function that takes an
    # output destination as an argument.

    # Inputs are each a 2-tuple of (basedir, pattern).

    # Lets add a rule to compile styles from a Sass source file (https://sass-lang.com/)
    # We only need to define one input, because the command is smart enough to
    # track how main.scss uses the `@import` CSS at-rule to include other files.

    (pyr.commands.scss('out/style.css'), [('styles', 'main.scss')]),

    # Let's add a rule to build indexes from all the markdown files in the
    # posts and pages folders

    # Rather than specify input names by hand, we can use wildcard/glob
    # patterns for free.

    # See mycommands.py to see how this command is implemented

    (mycommands.make_xml_index("out/posts.xml"), [('content', 'posts/**/*.md')]),
    (mycommands.make_xml_index("out/pages.xml"), [('content', 'pages/*.md'), ('content', 'pages/**/*.md')]),


    # Let's add a rule to build an output HTML page for all input pages
    # In this case, we're specifying an output directory instead of an output
    # file.

    # Using the basedir of "content" in each input tuple means we can easily
    # ignore this bit of the path, so we're writing "out/pages/..." rather than
    # "out/content/pages...".

    (mycommands.make_html_pages("out", index="out/posts.xml"), [('content', 'posts/**/*.md')]),
    (mycommands.make_html_pages("out", index="out/pages.xml"), [('content', 'pages/*.md'), ('content', 'pages/**/*.md')]),

] # end of rules array

# Now that we've defined our rules, we can turn them into a dependency graph.
# This lets us know what steps depend on other steps.

dag = pyr.rules.to_dag(rules)

# We can save this graph as an image using pydot.

dag.pydot("Dependency Graph").write_png("dag.png")

# In order to keep track of what work has already been done, we need to
# load a previous dag from disk, if one exists

try:
    with Path("lastrun.pyrrhic.txt").open("r") as fp:
        prev = pyr.rules.DAG.deserialize(fp.read())
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


# Save the previous build result
with Path("lastrun.pyrrhic.txt").open("w") as fp:
    fp.write(dag.serialize())


