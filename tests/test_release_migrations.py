import pytest

from ws.release.migrations import (
    MigrationUnreadable,
    Revision,
    chain_problems,
    containment_problems,
    heads,
    parse_revision,
    revisions,
    suggested_order,
)


def rev(r, *down):
    return Revision(r, tuple(down), f"m/{r}.py")


def tip(*items):
    return {i.revision: i for i in items}


def test_parse_revision_plain():
    src = 'revision = "b"\ndown_revision = "a"\n'
    assert parse_revision(src, "m/b.py") == Revision("b", ("a",), "m/b.py")


def test_parse_revision_annotated():
    src = 'from typing import Union\nrevision: str = "b"\ndown_revision: Union[str, None] = "a"\n'
    assert parse_revision(src, "p") == Revision("b", ("a",), "p")


def test_parse_revision_merge_tuple():
    src = 'revision = "d"\ndown_revision = ("b", "c")\n'
    assert parse_revision(src, "p").down == ("b", "c")


def test_parse_revision_merge_list():
    src = 'revision = "d"\ndown_revision = ["b", "c"]\n'
    assert parse_revision(src, "p").down == ("b", "c")


def test_parse_revision_first():
    src = 'revision = "a"\ndown_revision = None\n'
    assert parse_revision(src, "p").down == ()


def test_parse_revision_not_a_migration():
    assert parse_revision("x = 1\n", "p") is None


def test_parse_revision_syntax_error():
    with pytest.raises(MigrationUnreadable) as exc:
        parse_revision("def (:\n", "m/bad.py")
    assert "m/bad.py" in str(exc.value)


def test_parse_revision_non_literal():
    with pytest.raises(MigrationUnreadable) as exc:
        parse_revision('revision = "b"\ndown_revision = make()\n', "m/x.py")
    assert "m/x.py" in str(exc.value)


def test_revisions_skips_non_migrations():
    out = revisions({"m/a.py": 'revision = "a"\ndown_revision = None\n', "m/u.py": "x=1"})
    assert list(out) == ["a"]


def test_heads():
    a, b, c = rev("a"), rev("b", "a"), rev("c", "a")
    assert heads(tip(a, b, c)) == ["b", "c"]
    assert heads(tip(a, b, c, rev("d", "b", "c"))) == ["d"]


def test_chain_in_order_passes():
    a, b, c = rev("a"), rev("b", "a"), rev("c", "b")
    steps = [("TS-101", tip(a, b)), ("TS-102", tip(a, b, c))]
    assert chain_problems(tip(a), steps) == []


def test_chain_names_the_later_include():
    a, b, c = rev("a"), rev("b", "a"), rev("c", "b")
    steps = [("TS-102", tip(a, c)), ("TS-101", tip(a, b))]
    assert chain_problems(tip(a), steps) == [
        "TS-102: migration c needs b, which only TS-101 brings; merge TS-101 first"
    ]


def test_chain_missing_everywhere():
    a, c = rev("a"), rev("c", "zz")
    assert chain_problems(tip(a), [("TS-101", tip(a, c))]) == [
        "TS-101: migration c needs zz, which neither master nor an include has"
    ]


def test_chain_same_step_down_is_fine():
    a, b, c = rev("a"), rev("b", "a"), rev("c", "b")
    assert chain_problems(tip(a), [("TS-101", tip(a, b, c))]) == []


def test_containment_problems():
    assert containment_problems(["X", "Y"], {"X": {"Y"}, "Y": set()}) == [
        "X already contains Y; list Y before X"
    ]
    assert containment_problems(["Y", "X"], {"X": {"Y"}}) == []


def test_suggested_order_without_edges_keeps_the_list():
    assert suggested_order(["x", "y", "z"], set()) == (["x", "y", "z"], [])


def test_suggested_order_follows_edges():
    assert suggested_order(["x", "y", "z"], {("z", "x")}) == (["y", "z", "x"], [])


def test_suggested_order_cycle():
    order, problems = suggested_order(["x", "y"], {("x", "y"), ("y", "x")})
    assert order == ["x", "y"]
    assert problems == ["the order has a cycle: x, y"]
