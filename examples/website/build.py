import pyrrhic as pyr
from pathlib import Path

# Example build script for a simple static website.

# Usage: simply run as-is e.g. `python3 ./build.py` from the same directory.

# Our build script is a list of rules:
rules = [] # type: pyr.TRules

# Each rule takes the form of a 2-tuple (command, inputs).

# A command is usually implemented by a higher-order function that takes an
# output destination as an argument.

# Inputs are each a 2-tuple of (basedir, pattern).

# Lets add a rule to compile styles from a Sass source file (https://sass-lang.com/)

# There's a builtin to create the command for a given output. We only need to
# define one input, because the command is smart enough to track how main.scss
# imports other files.

rule = pyr.commands.scss('out/style.css'), [('styles', 'main.scss')] # type: pyr.TRule
rules.append(rule)

# Now that we've defined our rules, we can turn them into a dependency graph.
# This lets us know what steps depend on other steps.

dag = pyr.rules.to_dag(rules)

# We can save this graph as an image using pydot:
dag.pydot("Dependency Graph").write_png("dag.png")

# Load a previous dag, if it exists
try:
    with Path("lastrun.pyrrhic.txt").open("r") as fp:
        prev = pyr.rules.DAG.deserialize(fp.read())
except FileNotFoundError:
    prev = None

# Perform the build. The actual operations are lazy.
updates = dag.apply(prev)

for op, node in updates:
    # Each update is returned as a 2-tuple. The first argument is either "d"
    # for delete, or "w" for (over)write. This way you can prompt the user
    # to delete or overwrite first if you want to.

    print("%s %s" % (op, node.path))
    if op == "d":
        node.unlink()
    elif op == "w":
        node.apply()


# Save the previous build result
with Path("lastrun.pyrrhic.txt").open("w") as fp:
    fp.write(dag.serialize())


