import json
import os
import stat
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))

from gate import mcp_rules  # noqa: E402

GH = "mcp__plugin_github_github__"
JIRA = "mcp__plugin_productivity_atlassian__"
CLOUD = "mcp__claude_ai_Atlassian_MCP__"
KRAKEN = "mcp__plugin_gitkraken_gitkraken__"
FAKE_LEAK = "pass" + "word = hunter2abc"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("WS_CONFIG_DIR", str(config))
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("WS_GATE_WS_BIN", raising=False)
    return tmp_path


def set_owners(*owners: str) -> None:
    listed = ", ".join(json.dumps(owner) for owner in owners)
    path = Path(os.environ["WS_CONFIG_DIR"]) / "config.toml"
    path.write_text(f"[gate]\npersonal_github_owners = [{listed}]\n", encoding="utf-8")


def fake_ws(tmp_path: Path, exit_code: int, output: str = "") -> str:
    script = tmp_path / f"fake-ws-{exit_code}"
    lines = [
        "#!/bin/sh",
        f"echo '{output}'",
        'cp "$2" "$(dirname "$0")/seen.txt"',
        f"exit {exit_code}",
    ]
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script.chmod(0o755)
    return str(script)


def run(tool: str, **inputs):
    return mcp_rules.decide(tool, inputs, "/tmp")


def lines(decision) -> list[str]:
    return decision.reason.splitlines()


def test_catalog_tools_pass():
    assert run(GH + "get_file_contents", owner="a", repo="b").kind == "pass"
    assert run(KRAKEN + "git_commit", directory="/x").kind == "pass"
    assert run(JIRA + "getJiraIssue", issueIdOrKey="TS-1").kind == "pass"
    assert run("mcp__plugin_datadog_mcp__execute_code", code="1").kind == "pass"


def test_unlisted_tool_and_unknown_server_ask():
    assert run(GH + "brand_new_tool").kind == "ask"
    unknown = run("mcp__some_new_server__do_it", a=1)
    assert unknown.kind == "ask"
    assert lines(unknown)[0] == "Gravar fora — some_new_server"


def test_auth_only_servers_ask():
    assert run("mcp__claude_ai_Todoist__authenticate").kind == "ask"


def test_every_catalog_entry_is_a_string_list():
    data = json.loads(mcp_rules.CATALOG_PATH.read_text(encoding="utf-8"))
    assert data["version"] == 1
    for server, entry in data["servers"].items():
        assert entry["pass"] == sorted(set(entry["pass"])), server
    pass_names = {f"{s}__{t}" for s, e in data["servers"].items() for t in e["pass"]}
    assert not pass_names & {
        f"plugin_github_github__{t}" for t in ("push_files", "delete_repository")
    }


def test_the_user_scope_github_server_has_the_same_pass_list_as_the_plugin():
    servers = json.loads(mcp_rules.CATALOG_PATH.read_text(encoding="utf-8"))["servers"]
    assert servers["github"]["pass"] == servers["plugin_github_github"]["pass"]

    user_scope = "mcp__github__"
    assert run(user_scope + "get_me").kind == "pass"
    push = run(
        user_scope + "push_files",
        owner="o",
        repo="r",
        branch="b",
        message="m",
        files=[{"path": "a.md", "content": "1"}],
    )
    assert push.kind == "ask"
    assert lines(push)[0] == "Gravar fora — GitHub"
    assert "Enviar 1 arquivo(s) para o/r (branch b)" in lines(push)


@pytest.mark.parametrize("name", ["", "mcp__", "mcp__server", "mcp____tool", "other__a__b"])
def test_malformed_names_ask_generically(name):
    decision = mcp_rules.decide(name, {"k": "v"}, "/tmp")
    assert decision.kind == "ask"
    assert lines(decision)[0] == "Gravar fora — ferramenta MCP"


def test_github_create_pull_request():
    decision = run(
        GH + "create_pull_request",
        owner="octo",
        repo="repo",
        head="feature/x",
        base="main",
        title="docs: algo",
        body="Resumo\nlinha 2",
    )
    assert lines(decision)[:4] == [
        "Gravar fora — GitHub",
        "Criar PR em octo/repo: feature/x → main",
        "Título: docs: algo",
        'Corpo: 2 linhas (primeira: "Resumo")',
    ]


def test_github_merge_pull_request():
    decision = run(
        GH + "merge_pull_request", owner="o", repo="r", pullNumber=7, merge_method="squash"
    )
    assert "Mesclar o PR o/r#7" in lines(decision)
    assert "Método: squash" in lines(decision)


def test_github_file_writes():
    put = run(
        GH + "create_or_update_file",
        owner="o",
        repo="r",
        branch="b",
        path="a/b.md",
        message="msg",
        content="x\ny",
    )
    assert lines(put)[1:5] == [
        "Gravar arquivo em o/r (branch b)",
        "Caminho: a/b.md",
        "Mensagem: msg",
        'Conteúdo: 2 linhas (primeira: "x")',
    ]
    push = run(
        GH + "push_files",
        owner="o",
        repo="r",
        branch="b",
        message="m",
        files=[{"path": "a.md", "content": "1"}, {"path": "b.md", "content": "2"}],
    )
    assert "Enviar 2 arquivo(s) para o/r (branch b)" in lines(push)
    assert "Arquivos: a.md, b.md" in lines(push)
    gone = run(GH + "delete_file", owner="o", repo="r", branch="b", path="a.md", message="m")
    assert "Apagar arquivo em o/r (branch b)" in lines(gone)


def test_github_repository_level_writes():
    assert "Criar a branch nova em o/r, a partir de main" in lines(
        run(GH + "create_branch", owner="o", repo="r", branch="nova", from_branch="main")
    )
    created = run(GH + "create_repository", name="novo", private=True)
    assert "Criar o repositório novo (privado)" in lines(created)
    public = run(GH + "create_repository", name="novo")
    assert "PÚBLICO" in lines(public)[1]
    assert "APAGAR o repositório o/r (destrutivo, sem volta)" in lines(
        run(GH + "delete_repository", owner="o", repo="r")
    )
    assert "Copiar (fork) o repositório o/r para a sua conta" in lines(
        run(GH + "fork_repository", owner="o", repo="r")
    )


def test_github_issue_and_comment_writes():
    issue = run(GH + "issue_write", method="create", owner="o", repo="r", title="T", body="B")
    assert lines(issue)[1:4] == [
        "Criar issue em o/r",
        "Título: T",
        'Corpo: 1 linha (primeira: "B")',
    ]
    update = run(
        GH + "issue_write", method="update", issue_number=4, owner="o", repo="r", state="closed"
    )
    assert "Atualizar issue #4 em o/r" in lines(update)
    assert "Estado: closed" in lines(update)
    comment = run(GH + "add_issue_comment", owner="o", repo="r", issue_number=3, body="oi")
    assert "Comentar em o/r#3" in lines(comment)
    edit = run(GH + "update_issue_comment", owner="o", repo="r", comment_id=9, body="oi")
    assert "Editar o comentário 9 em o/r" in lines(edit)
    reply = run(
        GH + "add_reply_to_pull_request_comment",
        owner="o",
        repo="r",
        pullNumber=2,
        commentId=5,
        body="ok",
    )
    assert "Responder ao comentário 5 do PR o/r#2" in lines(reply)


def test_github_pull_request_edits():
    update = run(
        GH + "update_pull_request", owner="o", repo="r", pullNumber=2, title="T", state="closed"
    )
    assert "Alterar o PR o/r#2" in lines(update)
    assert "Campos: title, state" in lines(update)
    review = run(
        GH + "pull_request_review_write",
        method="create",
        owner="o",
        repo="r",
        pullNumber=2,
        event="APPROVE",
        body="b",
    )
    assert "Revisão (create) no PR o/r#2" in lines(review)
    assert "Evento: APPROVE" in lines(review)
    branch = run(GH + "update_pull_request_branch", owner="o", repo="r", pullNumber=2)
    assert "Atualizar a branch do PR o/r#2 com a base" in lines(branch)
    scan = run(GH + "run_secret_scanning", owner="o", repo="r", files=["a", "b"])
    assert "Trechos: 2" in lines(scan)


def test_jira_writes_on_both_servers():
    create = run(
        JIRA + "createJiraIssue",
        cloudId="c",
        projectKey="TS",
        issueTypeName="Task",
        summary="Resumo",
        description="Desc",
    )
    assert lines(create)[:3] == [
        "Gravar fora — Jira",
        "Criar issue no projeto TS (tipo Task)",
        "Resumo: Resumo",
    ]
    edit = run(
        CLOUD + "editJiraIssue",
        cloudId="c",
        issueIdOrKey="TS-1",
        fields={"summary": "x"},
        additional_fields={"Team": "y"},
    )
    assert "Alterar a issue TS-1" in lines(edit)
    assert "Campos: summary, Team" in lines(edit)
    move = run(JIRA + "transitionJiraIssue", issueIdOrKey="TS-1", transition={"id": "31"})
    assert "Transição: 31" in lines(move)
    comment = run(JIRA + "addCommentToJiraIssue", issueIdOrKey="TS-1", commentBody="oi")
    assert "Comentar em TS-1" in lines(comment)
    other = run(
        CLOUD + "addOrEditJiraIssueComment", issueIdOrKey="TS-1", commentId="5", commentBody="oi"
    )
    assert "Editar o comentário 5 em TS-1" in lines(other)
    worklog = run(JIRA + "addWorklogToJiraIssue", issueIdOrKey="TS-1", timeSpent="2h")
    assert "Tempo: 2h" in lines(worklog)
    link = run(JIRA + "createIssueLink", inwardIssue="TS-1", outwardIssue="TS-2", type="Blocks")
    assert "Ligar TS-1 e TS-2" in lines(link)


def test_atlassian_execute_calls_out_destructive():
    write = run(CLOUD + "executeWrite", name="doThing", inputs={"a": 1, "b": 2})
    assert "Operação: doThing" in lines(write)
    assert "Entradas: a, b" in lines(write)
    destructive = run(CLOUD + "executeDestructive", name="deleteThing", inputs={"id": 1})
    assert "Operação DESTRUTIVA: deleteThing" in lines(destructive)
    assert any("destrutiva" in line for line in lines(destructive))


def test_confluence_writes():
    create = run(
        JIRA + "createConfluencePage", cloudId="c", spaceId="12", title="Página", body="a\nb"
    )
    assert lines(create)[:3] == [
        "Gravar fora — Confluence",
        "Criar página no espaço 12",
        "Título: Página",
    ]
    update = run(
        CLOUD + "updateConfluenceContent",
        cloudId="c",
        contentId="77",
        title="Nova",
        body={"format": "html", "value": "<p>x</p>"},
    )
    assert "Alterar a página 77" in lines(update)
    made = run(
        CLOUD + "createConfluenceContent",
        cloudId="c",
        parent={"spaceId": "9"},
        contentType="page",
        title="T",
    )
    assert "Criar página no espaço 9" in lines(made)


def test_gitkraken_writes():
    push = run(KRAKEN + "git_push", directory="/work/repo")
    assert lines(push)[:3] == [
        "Gravar fora — GitKraken",
        "Enviar commits (git push)",
        "Pasta: /work/repo",
    ]
    pr = run(
        KRAKEN + "pull_request_create",
        repository_organization="o",
        repository_name="r",
        source_branch="a",
        target_branch="b",
        title="T",
        provider="github",
    )
    assert "Criar PR em o/r: a → b" in lines(pr)
    review = run(
        KRAKEN + "pull_request_create_review",
        repository_organization="o",
        repository_name="r",
        pull_request_id="4",
        review="ok",
        approve=True,
        provider="github",
    )
    assert "Revisão no PR 4 de o/r (aprovando)" in lines(review)
    issue = run(KRAKEN + "issues_create", provider="jira", title="T", repository_name="TS")
    assert "Criar issue (jira) em /TS" in lines(issue)
    comment = run(KRAKEN + "issues_add_comment", provider="github", issue_id="3", comment="c")
    assert "Comentar na issue 3 (github) em /" in lines(comment)


def test_generic_fallback_caps_lines_and_compacts_json():
    inputs = {f"k{i}": i for i in range(9)}
    inputs["k0"] = {"a": [1, 2]}
    decision = mcp_rules.decide("mcp__plugin_datadog_mcp__upsert_datadog_dashboard", inputs, "/tmp")
    shown = lines(decision)
    assert shown[0] == "Gravar fora — Datadog"
    assert shown[1] == "Ferramenta: upsert_datadog_dashboard"
    assert shown[2] == 'k0: {"a":[1,2]}'
    assert shown[-3] == "k5: 5"
    assert shown[-2] == "(+3 campos)"
    assert len(shown) == 10


def test_summary_survives_unexpected_shapes():
    decision = run(GH + "push_files", owner="o", repo="r", files="not a list")
    assert decision.kind == "ask"
    assert mcp_rules.decide(GH + "push_files", None, "/tmp").kind == "ask"


def test_no_owners_configured_asks_with_off_line():
    decision = run(
        GH + "create_pull_request", owner="octo", repo="r", head="a", base="b", title="T"
    )
    assert decision.kind == "ask"
    assert lines(decision)[-2] == mcp_rules.SIGILO_OFF


def test_non_personal_owner_has_no_sigilo_line(isolated_env):
    set_owners("me")
    decision = run(GH + "add_issue_comment", owner="company", repo="r", issue_number=1, body="x")
    assert "Sigilo" not in decision.reason


def test_clean_content_asks_with_checked_line(isolated_env):
    set_owners("Me")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, 0)
    decision = run(
        GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body="tudo certo"
    )
    assert decision.kind == "ask"
    assert lines(decision)[-2] == mcp_rules.SIGILO_CHECKED
    assert "tudo certo" in (isolated_env / "seen.txt").read_text(encoding="utf-8")


def test_finding_denies_with_the_output(isolated_env):
    set_owners("me")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(
        isolated_env, 1, "content:1: secret-assignment: password = ***"
    )
    decision = run(
        GH + "push_files",
        owner="me",
        repo="r",
        branch="b",
        message="m",
        files=[{"path": "a", "content": "x"}],
    )
    assert decision.kind == "deny"
    assert decision.reason.startswith("Blocked: content for the personal GitHub (me)")
    assert "secret-assignment" in decision.reason
    assert "ws mask" in decision.reason


def test_missing_ws_denies(isolated_env, monkeypatch):
    set_owners("me")
    monkeypatch.setenv("WS_GATE_WS_BIN", str(isolated_env / "does-not-exist"))
    decision = run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body="x")
    assert decision.kind == "deny"
    assert "could not run" in decision.reason


def test_no_ws_on_path_denies(isolated_env, monkeypatch):
    set_owners("me")
    monkeypatch.setattr(mcp_rules.shutil, "which", lambda name: None)
    monkeypatch.setattr(mcp_rules.Path, "home", classmethod(lambda cls: isolated_env / "nohome"))
    decision = run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body="x")
    assert decision.kind == "deny"
    assert "not found" in decision.reason


def test_timeout_denies(isolated_env, monkeypatch):
    set_owners("me")
    monkeypatch.setattr(mcp_rules, "CHECK_TIMEOUT_SECONDS", 0.2)
    slow = isolated_env / "slow-ws"
    slow.write_text("#!/bin/sh\nsleep 5\n", encoding="utf-8")
    slow.chmod(0o755)
    monkeypatch.setenv("WS_GATE_WS_BIN", str(slow))
    decision = run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body="x")
    assert decision.kind == "deny"
    assert "timed out" in decision.reason


def test_unreadable_config_denies(isolated_env):
    (Path(os.environ["WS_CONFIG_DIR"]) / "config.toml").write_text("[gate\n", encoding="utf-8")
    decision = run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body="x")
    assert decision.kind == "deny"


def test_temporary_file_is_removed_and_folder_is_private(isolated_env):
    set_owners("me")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, 1, "finding")
    run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body="x")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, 0)
    run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body="x")
    folder = isolated_env / "cache" / "gate"
    assert list(folder.iterdir()) == []
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700


def test_every_check_runs_in_a_fresh_private_repo(isolated_env):
    set_owners("me")
    probe = isolated_env / "cwd-ws"
    probe.write_text(
        "#!/bin/sh\n"
        'echo "$(pwd) $(stat -c %a .) $(test -d .git && echo repo) $(ls -A | wc -l)"'
        ' >> "$(dirname "$0")/cwds.txt"\n',
        encoding="utf-8",
    )
    probe.chmod(0o755)
    os.environ["WS_GATE_WS_BIN"] = str(probe)
    for _ in range(2):
        run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body="x")
    first, second = (isolated_env / "cwds.txt").read_text(encoding="utf-8").splitlines()
    assert first.split()[0] != second.split()[0]
    for entry in (first, second):
        assert entry.split()[1:] == ["700", "repo", "2"]
        assert not Path(entry.split()[0]).exists()


def test_a_planted_allowlist_does_not_excuse_a_finding(isolated_env):
    (Path(os.environ["WS_CONFIG_DIR"]) / "names.toml").write_text("", encoding="utf-8")
    set_owners("me")
    planted = isolated_env / "cache" / "gate"
    planted.mkdir(parents=True)
    (planted / ".secrets-allow").write_text("* secret-assignment hunter2abc\n", encoding="utf-8")
    dirty = run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body=FAKE_LEAK)
    assert dirty.kind == "deny"
    assert "secret-assignment" in dirty.reason


def test_temporary_file_is_mode_600_while_checked(isolated_env):
    set_owners("me")
    probe = isolated_env / "probe-ws"
    probe.write_text('#!/bin/sh\nstat -c %a "$2" > "$(dirname "$0")/mode.txt"\n', encoding="utf-8")
    probe.chmod(0o755)
    os.environ["WS_GATE_WS_BIN"] = str(probe)
    run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body="x")
    assert (isolated_env / "mode.txt").read_text(encoding="utf-8").strip() == "600"


def test_real_check_secrets(isolated_env):
    (Path(os.environ["WS_CONFIG_DIR"]) / "names.toml").write_text("", encoding="utf-8")
    set_owners("me")
    clean = run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body="tudo certo")
    assert clean.kind == "ask"
    dirty = run(GH + "add_issue_comment", owner="me", repo="r", issue_number=1, body=FAKE_LEAK)
    assert dirty.kind == "deny"
    assert "secret-assignment" in dirty.reason
    assert "hunter2abc" not in dirty.reason


KRAKEN_CHECKED_CALLS = {
    "pull_request_create": {"title": FAKE_LEAK, "source_branch": "a", "target_branch": "b"},
    "pull_request_create_review": {"review": FAKE_LEAK, "pull_request_id": "4"},
    "issues_create": {"title": FAKE_LEAK, "provider": "github"},
    "issues_add_comment": {"comment": FAKE_LEAK, "issue_id": "3", "provider": "github"},
}


@pytest.mark.parametrize("tool", sorted(KRAKEN_CHECKED_CALLS))
def test_gitkraken_writes_to_a_personal_owner_are_checked(isolated_env, tool):
    (Path(os.environ["WS_CONFIG_DIR"]) / "names.toml").write_text("", encoding="utf-8")
    set_owners("me")
    call = {**KRAKEN_CHECKED_CALLS[tool], "repository_organization": "Me", "repository_name": "r"}
    dirty = run(KRAKEN + tool, **call)
    assert dirty.kind == "deny"
    assert "secret-assignment" in dirty.reason
    clean = run(KRAKEN + tool, **{**call, "repository_organization": "company"})
    assert clean.kind == "ask"
    assert "Sigilo" not in clean.reason


def test_gitkraken_without_an_owner_is_checked_unless_the_provider_is_another(isolated_env):
    set_owners("me")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, 0)
    unknown = run(KRAKEN + "issues_add_comment", issue_id="3", comment="oi", provider="github")
    assert lines(unknown)[-2] == mcp_rules.SIGILO_CHECKED
    jira = run(KRAKEN + "issues_create", provider="jira", title="T", repository_name="TS")
    assert "Sigilo" not in jira.reason


def test_gitkraken_git_push_is_not_a_confidentiality_check(isolated_env):
    set_owners("me")
    assert "Sigilo" not in run(KRAKEN + "git_push", directory="/x").reason


def test_fork_is_checked_by_its_target_not_its_source(isolated_env):
    set_owners("me")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, 0)
    to_me = run(GH + "fork_repository", owner="company", repo="app", organization="me")
    assert lines(to_me)[-2] == mcp_rules.SIGILO_CHECKED
    assert "company/app" in (isolated_env / "seen.txt").read_text(encoding="utf-8")
    to_account = run(GH + "fork_repository", owner="company", repo="app")
    assert lines(to_account)[-2] == mcp_rules.SIGILO_CHECKED
    to_company = run(GH + "fork_repository", owner="me", repo="app", organization="company")
    assert "Sigilo" not in to_company.reason


def test_fork_with_a_finding_denies(isolated_env):
    set_owners("me")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, 1, "content:2: real-name: acme")
    decision = run(GH + "fork_repository", owner="acme", repo="app")
    assert decision.kind == "deny"
    assert "real-name" in decision.reason


@pytest.mark.parametrize("owner", [None, "", "  "])
def test_a_github_write_without_an_owner_is_checked(isolated_env, owner):
    set_owners("me")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, 0)
    call = {"repo": "r", "issue_number": 1, "body": "oi"}
    decision = run(GH + "add_issue_comment", **call, **({} if owner is None else {"owner": owner}))
    assert lines(decision)[-2] == mcp_rules.SIGILO_CHECKED
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, 1, "finding")
    blocked = run(GH + "add_issue_comment", **call)
    assert blocked.kind == "deny"
    assert "unknown owner" in blocked.reason


def test_a_github_write_without_an_owner_and_no_owners_configured_is_off():
    decision = run(GH + "add_issue_comment", repo="r", issue_number=1, body="oi")
    assert lines(decision)[-2] == mcp_rules.SIGILO_OFF


def unclassified_file() -> Path:
    return Path(os.environ["WS_DATA_DIR"]) / "gate" / "unclassified.json"


def test_catalog_ask_lists_are_sorted_and_never_overlap_pass():
    servers = json.loads(mcp_rules.CATALOG_PATH.read_text(encoding="utf-8"))["servers"]
    for server, entry in servers.items():
        assert entry["ask"] == sorted(set(entry["ask"])), server
        assert not set(entry["ask"]) & set(entry["pass"]), server


def test_a_tool_in_the_ask_list_asks_without_being_recorded():
    assert run(GH + "push_files", owner="o", repo="r", branch="b", files=[]).kind == "ask"
    assert run(CLOUD + "createJiraIssue", projectKey="TS").kind == "ask"
    assert not unclassified_file().exists()


def test_a_tool_that_passes_is_not_recorded():
    assert run(GH + "get_me").kind == "pass"
    assert not unclassified_file().exists()


def test_an_unclassified_tool_asks_and_is_recorded_with_a_count():
    assert run(GH + "brand_new_tool", note="hunter2").kind == "ask"
    assert run(GH + "brand_new_tool").kind == "ask"
    assert run("mcp__some_new_server__do_it", a=1).kind == "ask"

    data = json.loads(unclassified_file().read_text(encoding="utf-8"))
    assert set(data) == {"plugin_github_github", "some_new_server"}
    entry = data["plugin_github_github"]["brand_new_tool"]
    assert entry["count"] == 2
    assert len(entry["last"]) == 10
    assert "hunter2" not in unclassified_file().read_text(encoding="utf-8")


def test_the_record_folder_is_private_and_leaves_no_temp_file():
    run(GH + "brand_new_tool")

    folder = unclassified_file().parent
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert [path.name for path in folder.iterdir()] == ["unclassified.json"]


def test_the_record_stops_at_500_tools_but_keeps_counting_known_ones():
    path = unclassified_file()
    path.parent.mkdir(parents=True)
    tools = {f"tool_{n}": {"count": 1, "last": "2026-01-01"} for n in range(500)}
    path.write_text(json.dumps({"srv": tools}), encoding="utf-8")

    assert run("mcp__srv__one_more").kind == "ask"
    assert run("mcp__srv__tool_3").kind == "ask"

    data = json.loads(path.read_text(encoding="utf-8"))["srv"]
    assert "one_more" not in data
    assert data["tool_3"]["count"] == 2


@pytest.mark.parametrize("content", ["not json", "[1, 2]", '{"srv": 5}', '{"srv": {"t": 7}}'])
def test_a_damaged_record_is_replaced_not_fatal(content):
    path = unclassified_file()
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")

    assert run("mcp__srv__t").kind == "ask"

    assert json.loads(path.read_text(encoding="utf-8"))["srv"]["t"]["count"] == 1


def test_a_failure_to_record_never_changes_the_decision(tmp_path, monkeypatch):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("WS_DATA_DIR", str(blocker))

    decision = run(GH + "brand_new_tool")

    assert decision.kind == "ask"
    assert lines(decision)[0] == "Gravar fora — GitHub"


def test_names_that_are_not_plain_are_not_recorded():
    assert run("mcp__sr v__t").kind == "ask"
    assert run("mcp__srv__bad name").kind == "ask"
    assert not unclassified_file().exists()


def _personal_comment(**changes):
    inputs = {"owner": "me", "repo": "r", "issue_number": 1, "body": "x"} | changes
    return run(GH + "add_issue_comment", **inputs)


def _check_leftovers(isolated_env) -> list[str]:
    folder = isolated_env / "cache" / "gate"
    return [path.name for path in folder.iterdir()] if folder.exists() else []


def test_the_check_deadline_leaves_room_in_the_five_second_hook_limit():
    assert mcp_rules.CHECK_TIMEOUT_SECONDS == 3
    assert mcp_rules.CHECK_TIMEOUT_SECONDS + mcp_rules.GIT_INIT_TIMEOUT_SECONDS < 5


def test_a_check_that_takes_longer_than_three_seconds_denies(isolated_env):
    set_owners("me")
    slow = isolated_env / "slow-ws"
    slow.write_text("#!/bin/sh\nsleep 4\n", encoding="utf-8")
    slow.chmod(0o755)
    os.environ["WS_GATE_WS_BIN"] = str(slow)

    started = time.monotonic()
    decision = _personal_comment()

    assert time.monotonic() - started < 4
    assert decision.kind == "deny"
    assert "timed out" in decision.reason
    assert _check_leftovers(isolated_env) == []


def test_a_timeout_kills_what_the_check_started(isolated_env, monkeypatch):
    set_owners("me")
    monkeypatch.setattr(mcp_rules, "CHECK_TIMEOUT_SECONDS", 0.3)
    marker = isolated_env / "child-alive"
    slow = isolated_env / "forking-ws"
    slow.write_text(
        f"#!/bin/sh\n(sleep 1; touch '{marker}') &\nsleep 5\n",
        encoding="utf-8",
    )
    slow.chmod(0o755)
    os.environ["WS_GATE_WS_BIN"] = str(slow)

    assert _personal_comment().kind == "deny"

    time.sleep(1.5)
    assert not marker.exists()


def test_content_above_the_cap_denies_without_running_the_check(isolated_env):
    set_owners("me")
    ran = isolated_env / "ran"
    probe = isolated_env / "probe-ws"
    probe.write_text(f"#!/bin/sh\ntouch '{ran}'\n", encoding="utf-8")
    probe.chmod(0o755)
    os.environ["WS_GATE_WS_BIN"] = str(probe)

    decision = _personal_comment(body="a" * (mcp_rules.MAX_CHECK_BYTES + 1))

    assert decision.kind == "deny"
    assert "content too large to check" in decision.reason
    assert not ran.exists()
    assert _check_leftovers(isolated_env) == []


def test_the_cap_counts_bytes_not_characters(isolated_env):
    set_owners("me")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, 0)
    half = mcp_rules.MAX_CHECK_BYTES // 2

    assert _personal_comment(body="é" * (half - 100)).kind == "ask"
    assert _personal_comment(body="é" * (half + 1)).kind == "deny"


def test_a_lone_surrogate_never_crashes_the_check(isolated_env):
    set_owners("me")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, 0)

    assert _personal_comment(body="a\ud800b").kind in ("ask", "deny")
    assert _check_leftovers(isolated_env) == []


@pytest.mark.parametrize("exit_code", [0, 1])
def test_the_check_folder_is_gone_after_every_outcome(isolated_env, exit_code):
    set_owners("me")
    os.environ["WS_GATE_WS_BIN"] = fake_ws(isolated_env, exit_code, "finding")

    _personal_comment()

    assert _check_leftovers(isolated_env) == []


def test_a_symlinked_gate_folder_is_not_followed(isolated_env):
    target = isolated_env / "elsewhere"
    target.mkdir()
    gate = unclassified_file().parent
    gate.parent.mkdir(parents=True, exist_ok=True)
    gate.symlink_to(target)

    assert run(GH + "brand_new_tool").kind == "ask"

    assert list(target.iterdir()) == []
    assert gate.is_symlink()


def test_a_symlinked_record_file_is_not_followed_or_replaced(isolated_env):
    target = isolated_env / "victim.json"
    target.write_text('{"keep": {}}', encoding="utf-8")
    record = unclassified_file()
    record.parent.mkdir(parents=True)
    record.symlink_to(target)

    assert run(GH + "brand_new_tool").kind == "ask"

    assert target.read_text(encoding="utf-8") == '{"keep": {}}'
    assert record.is_symlink()
    assert [path.name for path in record.parent.iterdir()] == ["unclassified.json"]


def test_the_record_is_opened_with_o_nofollow(monkeypatch):
    flags: list[int] = []
    real_open = os.open

    def spy(path, flag, *args, **kwargs):
        flags.append(flag)
        return real_open(path, flag, *args, **kwargs)

    monkeypatch.setattr(mcp_rules.os, "open", spy)

    run(GH + "brand_new_tool")

    assert flags
    assert all(flag & os.O_NOFOLLOW for flag in flags)
    assert unclassified_file().exists()


ENVIRONMENT_POLICY = (
    '[gate]\nenvironment_branches = ["master", "main", "sandbox", "staging"]\n'
    'direct_push_repos = ["*-argocd"]\n'
)


def set_policy(extra: str = "") -> None:
    path = Path(os.environ["WS_CONFIG_DIR"]) / "config.toml"
    path.write_text(ENVIRONMENT_POLICY + extra, encoding="utf-8")


@pytest.mark.parametrize("tool", ["create_or_update_file", "push_files", "delete_file"])
@pytest.mark.parametrize(
    ("branch", "subject"),
    [("main", "main"), (None, "the default branch"), ("", "the default branch")],
)
def test_a_github_write_to_an_environment_branch_is_denied(tool, branch, subject):
    set_policy()
    inputs = {"owner": "o", "repo": "app", "path": "a.md", "message": "m", "content": "x"}
    if branch is not None:
        inputs["branch"] = branch
    decision = run(GH + tool, **inputs)

    assert decision.kind == "deny"
    assert decision.reason == (
        f"Blocked: {subject} is an environment branch of app; "
        "push a task branch and open a PR for the user to merge."
    )


def test_creating_an_environment_branch_is_denied():
    set_policy()

    assert run(GH + "create_branch", owner="o", repo="app", branch="staging").kind == "deny"


def test_a_github_write_in_an_argo_repo_asks_with_the_warning_on_top():
    set_policy()
    decision = run(
        GH + "create_or_update_file",
        owner="o",
        repo="deploy-argocd",
        branch="master",
        path="values.yaml",
        message="m",
        content="x",
    )

    assert decision.kind == "ask"
    assert lines(decision)[:3] == [
        "Gravar fora — GitHub",
        "ATENÇÃO: branch de ambiente master no repo deploy-argocd",
        "Gravar arquivo em o/deploy-argocd (branch master)",
    ]


def test_a_github_write_to_a_task_branch_or_with_the_policy_off_asks_as_before():
    set_policy()
    task = run(GH + "push_files", owner="o", repo="app", branch="feature/x", files=[], message="m")
    assert task.kind == "ask" and "ATENÇÃO" not in task.reason
    Path(os.environ["WS_CONFIG_DIR"], "config.toml").write_text("[gate]\n", encoding="utf-8")
    off = run(GH + "delete_file", owner="o", repo="app", branch="main", path="a", message="m")
    assert off.kind == "ask"


def test_the_environment_denial_comes_before_the_confidentiality_check(isolated_env):
    set_policy('personal_github_owners = ["me"]\n')
    os.environ["WS_GATE_WS_BIN"] = str(isolated_env / "missing-ws")
    decision = run(GH + "delete_file", owner="me", repo="app", branch="main", path="a", message="m")

    assert decision.kind == "deny"
    assert "environment branch" in decision.reason
