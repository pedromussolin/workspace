from datetime import date
from pathlib import Path

import pytest

from ws.cardstart import (
    RepoStep,
    StartRefused,
    branch_name,
    branch_slug,
    card_change,
    draft_text,
    is_task_branch,
    kind_for,
    resolve_repos,
    title_prefix,
    undo_commands,
)
from ws.taskmodel import Status


def test_branch_slug_drops_prefix_accents_and_stop_words():
    title = "[BACK] Fechar o lote por horário de corte do dia"
    assert branch_slug(title) == "fechar-lote-horario-corte-dia"


def test_branch_slug_cuts_at_a_word_within_40():
    title = "[FRONT] Exibir histórico completo das liquidações processadas automaticamente"
    assert branch_slug(title) == "exibir-historico-completo-liquidacoes"


def test_branch_slug_of_stop_words_only_is_empty():
    assert branch_slug("[FRONT] De a para o") == ""


def test_title_prefix():
    assert title_prefix("[BACK][API] x") == "BACK"
    assert title_prefix("Sem prefixo") is None


@pytest.mark.parametrize(
    ("card_type", "kind"),
    [
        ("bug", "fix"),
        ("task", "feature"),
        ("feature", "feature"),
        ("improvement", "feature"),
        ("hotfix", "feature"),
        (None, "feature"),
    ],
)
def test_kind_for_type(card_type, kind):
    assert kind_for(card_type) == kind


def test_branch_name():
    assert branch_name("fix", "TS-5", "a-b") == "fix/TS-5-a-b"


def test_resolve_repos_order():
    prefix = {"BACK": ("acme-api",), "FRONT": ("acme-front", "acme-api")}
    assert resolve_repos(["x", "y", "x"], ["a"], "[BACK] t", prefix) == (["x", "y"], "flag")
    assert resolve_repos([], ["a", "b", "a"], "[BACK] t", prefix) == (["a", "b"], "item")
    assert resolve_repos([], [], "[BACK] t", prefix) == ([], "item")
    assert resolve_repos([], None, "[FRONT] t", prefix) == (["acme-front", "acme-api"], "prefix")
    assert resolve_repos([], None, "[OPS] t", prefix) == ([], "none")
    assert resolve_repos([], None, "sem prefixo", prefix) == ([], "none")


@pytest.mark.parametrize(
    "name",
    ["feature/TS-5-x", "fix/TS-5-a-b"],
)
def test_is_task_branch_yes(name):
    assert is_task_branch(name, "TS-5")


@pytest.mark.parametrize(
    "name",
    ["feature/TS-55-x", "feature/TS-5-x-sdbx", "TS-5-x", "feature/TS-5", "wip/TS-5-x"],
)
def test_is_task_branch_no(name):
    assert not is_task_branch(name, "TS-5")


def test_card_change():
    start = date(2026, 11, 1)
    assert card_change(Status.TODO, None, True) == "move"
    assert card_change(Status.BLOCKED, start, True) == "move"
    for status in (Status.DONE, Status.CANCELLED):
        with pytest.raises(StartRefused, match=f"card is {status.value}: reopen it"):
            card_change(status, None, True)
    for status in (Status.IN_PROGRESS, Status.REVIEW, Status.VALIDATION, Status.READY_DEPLOY):
        assert card_change(status, None, True) == "start"
        assert card_change(status, None, False) is None
        assert card_change(status, start, True) is None


def test_draft_text_move_and_start():
    today = date(2026, 11, 16)
    assert draft_text("TS-5", "move", "Em andamento", today) == (
        '+++\nop = "move"\nkey = "TS-5"\nto = "Em andamento"\n+++\n'
    )
    assert draft_text("TS-5", "start", "Em andamento", today) == (
        '+++\nop = "edit"\nkey = "TS-5"\nstart = 2026-11-16\n+++\n'
    )


def step(action, **kw):
    base = {
        "name": "acme-api",
        "path": Path("/r/acme-api"),
        "base": "main",
        "action": action,
        "previous": "main",
        "detached": False,
        "worktree": None,
    }
    return RepoStep(**{**base, **kw})


def test_undo_commands():
    b = "feature/TS-5-x"
    created = ["git -C /r/acme-api switch main", f"git -C /r/acme-api branch -D {b}"]
    assert undo_commands([step("create")], b) == created
    assert undo_commands([step("track")], b) == created
    assert undo_commands([step("reuse")], b) == ["git -C /r/acme-api switch main"]
    assert undo_commands([step("current")], b) == []
    assert undo_commands([step("elsewhere")], b) == []
    wt = Path("/r/.worktrees/x")
    assert undo_commands([step("worktree", worktree=wt)], b) == [
        "git -C /r/acme-api worktree remove /r/.worktrees/x",
        f"git -C /r/acme-api branch -D {b}",
    ]
    assert undo_commands([step("reuse", previous="abc123", detached=True)], b) == [
        "git -C /r/acme-api switch --detach abc123"
    ]
    spaced = step("reuse", path=Path("/my repos/acme-api"))
    assert undo_commands([spaced], b) == ["git -C '/my repos/acme-api' switch main"]
