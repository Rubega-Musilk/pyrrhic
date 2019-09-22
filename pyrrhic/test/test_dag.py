import pytest
import pyrrhic as bw

deserialize = bw.rules.DAG.deserialize


def test_dag_hash():
    """Test that two identical constructions of a non-trivial function hash to
    the same result"""

    cmd_cons = bw.commands.cat
    hash_fn = bw.hash.function

    assert hash_fn(cmd_cons("foo")[0]) == hash_fn(cmd_cons("foo")[0])

    # Trivially, inequality:
    assert hash_fn(cmd_cons("foo")[0]) != hash_fn(cmd_cons("bar")[0])


def test_dag_eq():
    """Test that two DAGs constructed the same way compare equally."""

    rules1 = [
        (bw.commands.cat("bin/a"),  [("examples", "a")]),
        (bw.commands.cat("bin/b"),  [("examples", "b")]),
        (bw.commands.cat("bin/ab"), [("examples", "a"), ("examples", "b")]),
    ]

    rules2 = [
        (bw.commands.cat("bin/a"),  [("examples", "a")]),
        (bw.commands.cat("bin/b"),  [("examples", "b")]),
        (bw.commands.cat("bin/ab"), [("examples", "a"), ("examples", "b")]),
    ]

    rules3 = [
        (bw.commands.cat("bin/a"),  [("examples", "a")]),
        (bw.commands.cat("bin/b"),  [("examples", "b")]),
        (bw.commands.cat("bin/c"),  [("examples", "c")]),
        (bw.commands.cat("bin/ab"), [("examples", "a"), ("examples", "b")]),
    ]

    dag1 = bw.rules.to_dag(rules1)
    dag2 = bw.rules.to_dag(rules2)
    dag3 = bw.rules.to_dag(rules3)

    assert dag1 == dag2

    # Trivially, inequality:
    assert dag2 != dag3
    assert dag1 != dag3


def test_dag_serialise():
    """Test that a DAG serialises and deserialises to an equal representation.

    Note: this does not test for errors such as non-reproducible locals
    (like memory locations) leaking into the hash of commands. To test this
    fully would require a previously serialised DAG to be persisted to disk
    and checked across runs. However the symptoms would be fairly obvious: DAGs
    would reproducibly exhibit false-positives for differences.
    """

    dag = bw.rules.to_dag([
        (bw.commands.cat("bin/a"),   [("examples", "a")]),
        (bw.commands.cat("bin/b"),   [("examples", "b")]),
        (bw.commands.cat("bin/ab"),  [("examples", "a"), ("examples", "b")]),
    ])

    assert dag == deserialize(dag.serialize())


def test_dag_no_cycles():
    """Test that a DAG cannot contain cycles.

    On Python >= 3.7 you can catch a native RecursionError
    """

    with pytest.raises(bw.util.RecursionError):
        bw.rules.to_dag([
            (bw.commands.cat("a"),   [("", "a")]),
        ])

    with pytest.raises(bw.util.RecursionError):
        bw.rules.to_dag([
            (bw.commands.cat("b"),   [("", "a")]),
            (bw.commands.cat("c"),   [("", "b")]),
            (bw.commands.cat("a"),   [("", "c")]),
        ])


def test_dag_no_overwrite():
    """Test that a DAG cannot contain a rule where the same output is produced
    by more than one rule.
    """

    with pytest.raises(RuntimeError):
        bw.rules.to_dag([
            (bw.commands.cat("output"), [("", "a")]),
            (bw.commands.cat("output"), [("", "b")]),
        ])

    # but this is okay:
    bw.rules.to_dag([
        (bw.commands.cat("output1"), [("", "a")]),
        (bw.commands.cat("output2"), [("", "b")]),
    ])


def test_dag_mtimes():
    """Test applying a DAG with updated file mtimes generates the correct
    sequence of updates."""

    dag = bw.rules.to_dag([
        (bw.commands.cat("dest/a"),     [("src", "a")]),
        (bw.commands.cat("dest/b"),     [("src", "b")]),
        (bw.commands.cat("dest/c"),     [("src", "c")]),
        (bw.commands.cat("dest/ab"),    [("src", "a"), ("src", "b")]),
        (bw.commands.cat("dest/abc"),   [("src", "a"), ("src", "b"), ("src", "c")]),
        (bw.commands.cat("dest/a2"),    [("dest", "a")]),
        (bw.commands.cat("dest/b2"),    [("dest", "b")]),
        (bw.commands.cat("dest/a2b2"),  [("dest", "a"), ("dest", "b")]),
    ])

    # avoid disk and use these mtimes so that result is reproducable
    mtimes = {
        "src/a":         1.0, # exists
        "src/b":         1.0, # exists
        "src/c":         1.0, # exists
        "dest/a":       -1.0, # doesn't exist
        "dest/b":        2.0, # exists and up-to-date
        "dest/c":       -1.0, # doesn't exist
        "dest/ab":      -1.0, # doesn't exist
        "dest/abc":     -1.0, # doesn't exist
        "dest/a2":       3.0, # exists, should be updated regardless
        "dest/b2":      -1.0, # doesn't exist
        "dest/a2b2":     3.0, # exists, should be updated regardless
    }

    results = dag.apply(dag, _mtimes=mtimes)
    results = [(op, str(node.path)) for op, node in results]

    # Note result ordering is from DFS with nodes at the same depth sorted
    # alphabetically by path
    assert results == [
        ("w", "dest/a"),
        ("w", "dest/a2"),
        ("w", "dest/a2b2"),
        ("w", "dest/ab"),
        ("w", "dest/abc"),
        ("w", "dest/b2"),
        ("w", "dest/c"),
    ]


def test_dag_diff():
    """Test applying a DAG against a history generates the correct updates."""

    dag1 = bw.rules.to_dag([
        (bw.commands.cat("dest/a"),     [("src", "a")]),
        (bw.commands.cat("dest/b"),     [("src", "b")]),
        (bw.commands.cat("dest/c"),     [("src", "c")]),
        # d removed
        # d2 removed
        (bw.commands.cat("dest/e"),     [("src", "e")]),  # new
        (bw.commands.cat("dest/e2"),    [("dest", "e")]), # new
    ])

    dag2 = bw.rules.to_dag([
        (bw.commands.cat("dest/a"),     [("src", "a")]),
        (bw.commands.cat("dest/b"),     [("src", "b")]),
        (bw.commands.cat("dest/c"),     [("src", "c")]),
        (bw.commands.cat("dest/d"),     [("src", "d")]),
        (bw.commands.cat("dest/d2"),    [("dest", "d")]),
    ])

    # avoid disk and use these mtimes so that result is reproducable
    mtimes = {
        "src/a":        1.0, # exists
        "dest/a":       2.0, # exists, up to date
        "src/b":        1.0, # exists
        "dest/b":       2.0, # exists, up to date
        "src/c":        1.0, # exists
        "dest/c":       2.0, # exists, up to date
        "src/d":        1.0, # exists
        "dest/d":       2.0, # exists, up to date
        "dest/d2":      3.0, # exists, up to date
        "src/e":        1.0, # exists
        "dest/e":       2.0, # exists, up to date
        "dest/e2":      3.0, # exists, up to date
    }

    results = dag1.apply(dag2, _mtimes=mtimes)
    results = [(op, str(node.path)) for op, node in results]

    # Note result ordering is from DFS with nodes at the same depth sorted
    # alphabetically by path, but with deletes ordered first
    assert results == [
        ("d", "dest/d"),
        ("d", "dest/d2"),
        ("w", "dest/e"),
        ("w", "dest/e2"),
    ]

