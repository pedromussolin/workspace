"""MCP rules of the gate: catalog lookup, the PT-BR summary of each write and the sigilo check.

`decide` passes a tool the catalog lists under its server and asks for everything else, so a tool
nobody classified yet asks (fail closed). A GitHub write (the GitHub MCP, and the GitKraken tools
that create PRs, reviews, issues and comments) whose owner is one of the personal accounts, or
whose owner the call does not say, also has its text checked with `ws check-secrets` before the
box is shown.
"""

import json
import os
import shutil
import subprocess
import tempfile
import tomllib
from collections.abc import Callable
from pathlib import Path

from .decision import PASS, Decision, ask, body_summary, cut, deny

CATALOG_PATH = Path(__file__).with_name("catalog.json")
CHECK_TIMEOUT_SECONDS = 20
GENERIC_LINES = 6
PLAIN_KEYS = frozenset({"owner", "repo"})
DESTINATION_KEYS = PLAIN_KEYS | {"repository_organization", "repository_name"}
KRAKEN_CHECKED = frozenset(
    {"pull_request_create", "pull_request_create_review", "issues_create", "issues_add_comment"}
)

SIGILO_CHECKED = "Sigilo: conferido (check-secrets)"
SIGILO_OFF = "Sigilo: conferência desligada (sem personal_github_owners)"


def _load_catalog() -> dict[str, set[str]]:
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return {server: set(entry["pass"]) for server, entry in data["servers"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def _text(inputs: dict, key: str) -> str:
    value = inputs.get(key)
    return "" if value is None else str(value)


def _line(label: str, value: object) -> list[str]:
    text = "" if value is None else str(value)
    return [f"{label}: {cut(text)}"] if text.strip() else []


def _body(label: str, value: object) -> list[str]:
    text = "" if value is None else str(value)
    return [f"{label}: {body_summary(text)}"] if text.strip() else []


def _compact(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _generic(tool: str, inputs: dict) -> list[str]:
    lines = [f"Ferramenta: {tool}"]
    items = list(inputs.items())
    for key, value in items[:GENERIC_LINES]:
        lines.append(f"{key}: {cut(_compact(value))}")
    if len(items) > GENERIC_LINES:
        lines.append(f"(+{len(items) - GENERIC_LINES} campos)")
    return lines


def _where(inputs: dict) -> str:
    return f"{_text(inputs, 'owner')}/{_text(inputs, 'repo')}"


def _issue_ref(inputs: dict, *keys: str) -> str:
    number = next((inputs[key] for key in keys if inputs.get(key) is not None), "?")
    return f"{_where(inputs)}#{number}"


def _github_create_pull_request(inputs: dict) -> list[str]:
    head, base = _text(inputs, "head"), _text(inputs, "base")
    lines = [f"Criar PR em {_where(inputs)}: {head} → {base}"]
    if inputs.get("draft"):
        lines.append("Rascunho (draft)")
    return lines + _line("Título", inputs.get("title")) + _body("Corpo", inputs.get("body"))


def _github_merge_pull_request(inputs: dict) -> list[str]:
    method = _text(inputs, "merge_method") or "merge (padrão)"
    return (
        [f"Mesclar o PR {_issue_ref(inputs, 'pullNumber')}", f"Método: {method}"]
        + _line("Título do commit", inputs.get("commit_title"))
        + _body("Mensagem do commit", inputs.get("commit_message"))
    )


def _github_create_or_update_file(inputs: dict) -> list[str]:
    return (
        [f"Gravar arquivo em {_where(inputs)} (branch {_text(inputs, 'branch')})"]
        + _line("Caminho", inputs.get("path"))
        + _line("Mensagem", inputs.get("message"))
        + _body("Conteúdo", inputs.get("content"))
    )


def _github_push_files(inputs: dict) -> list[str]:
    files = inputs.get("files")
    entries = files if isinstance(files, list) else []
    paths = [str(entry.get("path", "?")) for entry in entries if isinstance(entry, dict)]
    return (
        [f"Enviar {len(paths)} arquivo(s) para {_where(inputs)} (branch {_text(inputs, 'branch')})"]
        + _line("Arquivos", ", ".join(paths))
        + _line("Mensagem", inputs.get("message"))
    )


def _github_delete_file(inputs: dict) -> list[str]:
    return (
        [f"Apagar arquivo em {_where(inputs)} (branch {_text(inputs, 'branch')})"]
        + _line("Caminho", inputs.get("path"))
        + _line("Mensagem", inputs.get("message"))
    )


def _github_create_branch(inputs: dict) -> list[str]:
    origin = _text(inputs, "from_branch") or "a branch padrão"
    return [f"Criar a branch {_text(inputs, 'branch')} em {_where(inputs)}, a partir de {origin}"]


def _github_create_repository(inputs: dict) -> list[str]:
    visibility = "privado" if inputs.get("private") else "PÚBLICO (ou padrão da conta)"
    lines = [f"Criar o repositório {_text(inputs, 'name')} ({visibility})"]
    return (
        lines
        + _line("Organização", inputs.get("organization"))
        + _line("Descrição", inputs.get("description"))
    )


def _github_delete_repository(inputs: dict) -> list[str]:
    return [f"APAGAR o repositório {_where(inputs)} (destrutivo, sem volta)"]


def _github_fork_repository(inputs: dict) -> list[str]:
    target = _text(inputs, "organization") or "a sua conta"
    return [f"Copiar (fork) o repositório {_where(inputs)} para {target}"]


def _github_issue_write(inputs: dict) -> list[str]:
    method = _text(inputs, "method")
    number = inputs.get("issue_number")
    verb = "Criar issue" if method == "create" else f"Atualizar issue #{number}"
    return (
        [f"{verb} em {_where(inputs)}"]
        + _line("Título", inputs.get("title"))
        + _body("Corpo", inputs.get("body"))
        + _line("Estado", inputs.get("state"))
    )


def _github_add_issue_comment(inputs: dict) -> list[str]:
    return [f"Comentar em {_issue_ref(inputs, 'issue_number')}"] + _body(
        "Texto", inputs.get("body")
    )


def _github_update_issue_comment(inputs: dict) -> list[str]:
    where = f"Editar o comentário {_text(inputs, 'comment_id')} em {_where(inputs)}"
    return [where] + _body("Texto", inputs.get("body"))


def _github_add_reply(inputs: dict) -> list[str]:
    comment, pull = _text(inputs, "commentId"), _issue_ref(inputs, "pullNumber")
    where = f"Responder ao comentário {comment} do PR {pull}"
    return [where] + _body("Texto", inputs.get("body")) + _line("Reação", inputs.get("reaction"))


def _github_update_pull_request(inputs: dict) -> list[str]:
    changed = [key for key in inputs if key not in PLAIN_KEYS | {"pullNumber"}]
    return (
        [f"Alterar o PR {_issue_ref(inputs, 'pullNumber')}"]
        + _line("Campos", ", ".join(changed))
        + _line("Título", inputs.get("title"))
        + _body("Corpo", inputs.get("body"))
        + _line("Estado", inputs.get("state"))
        + _line("Base", inputs.get("base"))
    )


def _github_review_write(inputs: dict) -> list[str]:
    head = f"Revisão ({_text(inputs, 'method')}) no PR {_issue_ref(inputs, 'pullNumber')}"
    return [head] + _line("Evento", inputs.get("event")) + _body("Texto", inputs.get("body"))


def _github_update_pr_branch(inputs: dict) -> list[str]:
    return [f"Atualizar a branch do PR {_issue_ref(inputs, 'pullNumber')} com a base"]


def _github_secret_scanning(inputs: dict) -> list[str]:
    files = inputs.get("files")
    count = len(files) if isinstance(files, list) else 1
    return [
        f"Enviar conteúdo ao GitHub ({_where(inputs)}) para varredura de segredos",
        f"Trechos: {count}",
    ]


GITHUB = {
    "create_pull_request": _github_create_pull_request,
    "merge_pull_request": _github_merge_pull_request,
    "create_or_update_file": _github_create_or_update_file,
    "push_files": _github_push_files,
    "delete_file": _github_delete_file,
    "create_branch": _github_create_branch,
    "create_repository": _github_create_repository,
    "delete_repository": _github_delete_repository,
    "fork_repository": _github_fork_repository,
    "issue_write": _github_issue_write,
    "add_issue_comment": _github_add_issue_comment,
    "update_issue_comment": _github_update_issue_comment,
    "add_reply_to_pull_request_comment": _github_add_reply,
    "update_pull_request": _github_update_pull_request,
    "pull_request_review_write": _github_review_write,
    "update_pull_request_branch": _github_update_pr_branch,
}

GITHUB["run_secret_scanning"] = _github_secret_scanning


def _issue_key(inputs: dict) -> str:
    return _text(inputs, "issueIdOrKey") or _text(inputs, "issueKey") or "?"


def _jira_create_issue(inputs: dict) -> list[str]:
    kind = _text(inputs, "issueTypeName") or _text(inputs, "issueType")
    project = _text(inputs, "projectKey")
    head = f"Criar issue no projeto {project}" + (f" (tipo {kind})" if kind else "")
    return (
        [head]
        + _line("Resumo", inputs.get("summary"))
        + _body("Descrição", inputs.get("description"))
    )


def _jira_edit_issue(inputs: dict) -> list[str]:
    names: list[str] = []
    for key in ("fields", "additional_fields"):
        value = inputs.get(key)
        if isinstance(value, dict):
            names.extend(str(name) for name in value)
    return [f"Alterar a issue {_issue_key(inputs)}"] + _line("Campos", ", ".join(names))


def _jira_transition(inputs: dict) -> list[str]:
    transition = inputs.get("transition")
    ident = transition.get("id") if isinstance(transition, dict) else None
    ident = ident or inputs.get("transitionId") or inputs.get("transitionName")
    return [f"Mover a issue {_issue_key(inputs)} de status"] + _line("Transição", ident)


def _jira_comment(inputs: dict) -> list[str]:
    edit = inputs.get("commentId")
    verb = f"Editar o comentário {edit} em" if edit else "Comentar em"
    body = inputs.get("commentBody")
    return [f"{verb} {_issue_key(inputs)}"] + _body("Texto", body)


def _jira_worklog(inputs: dict) -> list[str]:
    return (
        [f"Registrar tempo em {_issue_key(inputs)}"]
        + _line("Tempo", inputs.get("timeSpent"))
        + _body("Comentário", inputs.get("commentBody"))
    )


def _jira_issue_link(inputs: dict) -> list[str]:
    head = f"Ligar {_text(inputs, 'inwardIssue')} e {_text(inputs, 'outwardIssue')}"
    return [head] + _line("Tipo", inputs.get("type")) + _body("Comentário", inputs.get("comment"))


def _jira_execute(destructive: bool) -> Callable[[dict], list[str]]:
    def summary(inputs: dict) -> list[str]:
        operation = _text(inputs, "name")
        inner = inputs.get("inputs")
        keys = ", ".join(str(key) for key in inner) if isinstance(inner, dict) else ""
        label = "Operação DESTRUTIVA" if destructive else "Operação"
        lines = _line(label, operation) + _line("Entradas", keys)
        return lines + (
            ["Esta operação é destrutiva (apaga ou não tem volta)"] if destructive else []
        )

    return summary


def _confluence_create(inputs: dict) -> list[str]:
    parent = inputs.get("parent")
    space = inputs.get("spaceId") or (parent.get("spaceId") if isinstance(parent, dict) else None)
    body = inputs.get("body")
    text = body.get("value") if isinstance(body, dict) else body
    head = f"Criar página no espaço {space if space else '?'}"
    return [head] + _line("Título", inputs.get("title")) + _body("Corpo", text)


def _confluence_update(inputs: dict) -> list[str]:
    page = inputs.get("pageId") or inputs.get("contentId") or inputs.get("contentUrl")
    body = inputs.get("body")
    text = body.get("value") if isinstance(body, dict) else body
    head = f"Alterar a página {page if page else '?'}"
    return [head] + _line("Título", inputs.get("title")) + _body("Corpo", text)


ATLASSIAN = {
    "createJiraIssue": _jira_create_issue,
    "editJiraIssue": _jira_edit_issue,
    "transitionJiraIssue": _jira_transition,
    "addCommentToJiraIssue": _jira_comment,
    "addOrEditJiraIssueComment": _jira_comment,
    "addWorklogToJiraIssue": _jira_worklog,
    "createIssueLink": _jira_issue_link,
    "executeWrite": _jira_execute(False),
    "executeDestructive": _jira_execute(True),
    "createConfluencePage": _confluence_create,
    "createConfluenceContent": _confluence_create,
    "updateConfluencePage": _confluence_update,
    "updateConfluenceContent": _confluence_update,
}


def _kraken_repo(inputs: dict) -> str:
    return f"{_text(inputs, 'repository_organization')}/{_text(inputs, 'repository_name')}"


def _kraken_push(inputs: dict) -> list[str]:
    return ["Enviar commits (git push)"] + _line("Pasta", inputs.get("directory"))


def _kraken_pull_request(inputs: dict) -> list[str]:
    source, target = _text(inputs, "source_branch"), _text(inputs, "target_branch")
    head = f"Criar PR em {_kraken_repo(inputs)}: {source} → {target}"
    return [head] + _line("Título", inputs.get("title")) + _body("Corpo", inputs.get("body"))


def _kraken_review(inputs: dict) -> list[str]:
    head = f"Revisão no PR {_text(inputs, 'pull_request_id')} de {_kraken_repo(inputs)}"
    lines = [head + (" (aprovando)" if inputs.get("approve") else "")]
    return lines + _body("Texto", inputs.get("review"))


def _kraken_issue_create(inputs: dict) -> list[str]:
    head = f"Criar issue ({_text(inputs, 'provider')}) em {_kraken_repo(inputs)}"
    return [head] + _line("Título", inputs.get("title")) + _body("Corpo", inputs.get("body"))


def _kraken_issue_comment(inputs: dict) -> list[str]:
    issue, provider = _text(inputs, "issue_id"), _text(inputs, "provider")
    head = f"Comentar na issue {issue} ({provider}) em {_kraken_repo(inputs)}"
    return [head] + _body("Texto", inputs.get("comment"))


GITKRAKEN = {
    "git_push": _kraken_push,
    "pull_request_create": _kraken_pull_request,
    "pull_request_create_review": _kraken_review,
    "issues_create": _kraken_issue_create,
    "issues_add_comment": _kraken_issue_comment,
}


def _family(server: str) -> str:
    lowered = server.lower()
    for name in ("github", "atlassian", "gitkraken", "datadog"):
        if name in lowered:
            return name
    return "claude_docs" if "claude_docs" in lowered else ""


def _service(server: str, tool: str) -> str:
    family = _family(server)
    if family == "atlassian":
        return "Confluence" if "confluence" in tool.lower() else "Jira"
    return {
        "github": "GitHub",
        "gitkraken": "GitKraken",
        "datadog": "Datadog",
        "claude_docs": "Claude Docs",
    }.get(family, server)


def _summary(server: str, tool: str, inputs: dict) -> list[str]:
    table = {"github": GITHUB, "atlassian": ATLASSIAN, "gitkraken": GITKRAKEN}.get(_family(server))
    builder = table.get(tool) if table else None
    if builder is None:
        return _generic(tool, inputs)
    try:
        return builder(inputs)
    except (AttributeError, TypeError, ValueError):
        return _generic(tool, inputs)


def _config_dir() -> Path:
    value = os.environ.get("WS_CONFIG_DIR")
    return Path(value) if value else Path.home() / ".config" / "workspace"


def _cache_dir() -> Path:
    value = os.environ.get("WS_CACHE_DIR")
    return Path(value) if value else Path.home() / ".cache" / "workspace"


def personal_owners() -> frozenset[str] | None:
    """The `[gate] personal_github_owners` of config.toml, lowercased; None when not configured.

    A config that exists but cannot be read raises ValueError, so the caller blocks.
    """
    path = _config_dir() / "config.toml"
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"config.toml unreadable ({error})") from error
    owners = data.get("gate", {}).get("personal_github_owners")
    if not isinstance(owners, list) or not owners:
        return None
    return frozenset(str(owner).lower() for owner in owners)


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def sent_text(inputs: dict) -> str:
    """Every string the call sends (contents, paths, titles, bodies, messages); the destination
    (owner and repo) is left out."""
    parts = [
        text
        for key, value in inputs.items()
        if key not in DESTINATION_KEYS
        for text in _strings(value)
    ]
    return "\n".join(parts)


def _ws_binary() -> str | None:
    override = os.environ.get("WS_GATE_WS_BIN")
    if override:
        return override
    found = shutil.which("ws")
    if found:
        return found
    local = Path.home() / ".local" / "bin" / "ws"
    return str(local) if local.exists() else None


def _fresh_repo() -> Path:
    """A new private folder that is its own git repo: `ws check-secrets PATH` needs a repo as its
    cwd, and a folder made for this one check cannot hold a `.secrets-allow` planted earlier."""
    parent = _cache_dir() / "gate"
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    parent.chmod(0o700)
    folder = Path(tempfile.mkdtemp(prefix="check-", dir=parent))
    try:
        subprocess.run(
            ["git", "init", "-q"], cwd=folder, check=True, capture_output=True, timeout=10
        )
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return folder


def check_secrets(text: str) -> str | None:
    """None when `ws check-secrets` finds nothing; otherwise why the content cannot go."""
    binary = _ws_binary()
    if binary is None:
        return "ws executable not found"
    try:
        folder = _fresh_repo()
    except (OSError, subprocess.SubprocessError) as error:
        return f"could not prepare the check folder ({error})"
    try:
        descriptor, name = tempfile.mkstemp(dir=folder, prefix="content-", suffix=".txt")
        path = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        try:
            result = subprocess.run(
                [binary, "check-secrets", str(path)],
                cwd=folder,
                capture_output=True,
                text=True,
                timeout=CHECK_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return f"ws check-secrets timed out after {CHECK_TIMEOUT_SECONDS}s"
        except OSError as error:
            return f"ws check-secrets could not run ({error})"
        if result.returncode == 0:
            return None
        output = (result.stdout + result.stderr).strip().replace(str(path), "content")
        return cut(output, 500) or f"ws check-secrets exited {result.returncode}"
    except OSError as error:
        return f"could not prepare the check folder ({error})"
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _destination(family: str, tool: str, inputs: dict) -> str:
    """The lowercased account the write lands on; empty when the call does not say (the
    authenticated account for a create or a fork, or simply missing)."""
    if family == "gitkraken":
        key = "repository_organization"
    elif tool in ("create_repository", "fork_repository"):
        key = "organization"
    else:
        key = "owner"
    return _text(inputs, key).strip().lower()


def _confidentiality(family: str, tool: str, inputs: dict) -> tuple[Decision | None, str]:
    """A `deny`, or None with the box line that says how the content was checked."""
    try:
        owners = personal_owners()
    except ValueError as error:
        return deny(f"Blocked: cannot tell whether the GitHub owner is personal: {error}."), ""
    if owners is None:
        return None, SIGILO_OFF
    owner = _destination(family, tool, inputs)
    provider = _text(inputs, "provider").strip().lower()
    if family == "gitkraken" and not owner and provider not in ("", "github"):
        return None, ""
    if owner and owner not in owners:
        return None, ""
    text = sent_text(inputs)
    if tool == "fork_repository":
        text += f"\n{_where(inputs)}"
    problem = check_secrets(text)
    if problem is not None:
        shown = owner or "unknown owner or authenticated account"
        return (
            deny(
                f"Blocked: content for the personal GitHub ({shown}) has check-secrets "
                f"findings: {problem}; mask it with ws mask and retry."
            ),
            "",
        )
    return None, SIGILO_CHECKED


def decide(tool_name: str, tool_input: dict, cwd: str) -> Decision:
    inputs = tool_input if isinstance(tool_input, dict) else {}
    parts = str(tool_name).split("__", 2)
    if len(parts) != 3 or parts[0] != "mcp" or not parts[1] or not parts[2]:
        return ask(
            "Gravar fora — ferramenta MCP",
            [
                f"Nome de ferramenta não reconhecido: {cut(tool_name)}",
                *_generic(str(tool_name), inputs)[1:],
            ],
        )
    _, server, tool = parts
    if tool in _load_catalog().get(server, set()):
        return PASS
    lines = _summary(server, tool, inputs)
    sigilo = ""
    family = _family(server)
    if family == "github" or (family == "gitkraken" and tool in KRAKEN_CHECKED):
        blocked, sigilo = _confidentiality(family, tool, inputs)
        if blocked is not None:
            return blocked
    if sigilo:
        lines = [*lines[:7], sigilo]
    return ask(f"Gravar fora — {_service(server, tool)}", lines)
