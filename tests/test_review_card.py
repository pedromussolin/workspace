from fake_tracker import FakeTracker, make_card

from ws.reviewcard import card_context, done_when
from ws.taskmodel import Status
from ws.tracker.jira.adapter import JIRA_CAPABILITIES

TEXT = "## Contexto\nx\n## Pronto quando\n- a\n- b\n## Como reproduzir\ny"


def test_done_when_takes_the_section_until_the_next_heading():
    assert done_when(TEXT) == "- a\n- b"
    assert done_when("### pronto QUANDO\n- z\n") == "- z"
    assert done_when("## Contexto\nx") is None
    assert done_when("## Pronto quando\n\n## Outro\ny") is None


def test_card_context_reads_the_card():
    card = make_card("TS-1", title="Tela x", type="improvement", status=Status.REVIEW)
    tracker = FakeTracker([card], descriptions={"TS-1": TEXT})

    context, warnings = card_context(tracker, "TS-1")

    assert context == {
        "ref": "TS-1",
        "title": "Tela x",
        "type": "improvement",
        "status": "review",
        "done_when": "- a\n- b",
    }
    assert warnings == []


def test_card_context_without_the_capability_warns():
    tracker = FakeTracker(
        [make_card("TS-1")],
        capabilities=JIRA_CAPABILITIES - {"description"},
        descriptions={"TS-1": TEXT},
    )

    context, warnings = card_context(tracker, "TS-1")

    assert context["done_when"] is None
    assert warnings == ["the tracker gives no card description; read Pronto quando in the tracker"]


def test_card_context_warns_when_there_is_no_section():
    tracker = FakeTracker([make_card("TS-1")], descriptions={"TS-1": "## Contexto\nx"})

    context, warnings = card_context(tracker, "TS-1")

    assert context["done_when"] is None
    assert warnings == ["TS-1 has no Pronto quando section"]


def test_card_context_absent_card():
    assert card_context(FakeTracker(), "TS-9") == (None, [])


def test_done_when_keeps_a_code_block_with_a_comment():
    text = "## Pronto quando\n- a\n```\n# comment\nx = 1\n```\n- b\n## Outro\ny"

    assert done_when(text) == "- a\n```\n# comment\nx = 1\n```\n- b"


def test_card_context_with_an_empty_description_warns():
    tracker = FakeTracker([make_card("TS-1")], descriptions={"TS-1": ""})

    context, warnings = card_context(tracker, "TS-1")

    assert context["done_when"] is None
    assert warnings == ["TS-1 has no Pronto quando section"]
