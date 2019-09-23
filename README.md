Pyrrhic
=======

Pyrrhic is a programmable Python build system that supports incremental
compilation, dynamic dependencies, and powerful builtins for a range of tasks.

![Dependency Graph](examples/website/dag-example.png)


Features
--------

### Programmable

* Build commands are short Python functions

* Build rules are a Python list of (command, inputs) tuples

### Dynamic dependencies

* Pyrrhic automatically detects additional file dependencies without you having
to name them explicitly

* Pyrrhic automatically knows that if input "A" produces output "B", and input
"B" produces output "C", then output "C" also depends on "A".

* Pyrrhic doesn't just track files: it also tracks the Python bytecode of the
command used to create an output! Change how a build command is implemented,
and Pyrrhic knows to update the target.

### Correct and minimal

Pyrrhic keeps the system up to date (correct) with the minimum of work. It will
always apply the smallest subtree of a dependency graph. It will delete stale
outputs. If nothing changes, then pyrrhic does nothing!

### Handy builtins

* `pyrrhic.commands.cat`: concatenate files with optional transformations
* `pyrrhic.commands.copy`: copy files with optional transformations
* `pyrrhic.commands.compile_file`: generic command to compile a file and track dependencies
* `pyrrhic.commands.scss`: compile SCSS⮕CSS (`pip install libsass`)


Usage
-----

See examples folder.

Tutorials coming soon...

