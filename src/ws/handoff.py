"""Handoff of a chat to a new one (part A of the session automations spec).

`collect` reads the state of the repos, worktrees and open PRs; `find_handoffs` lists the handoff
files the session hook points at. Everything here is read-only except `new_handoff` and `refresh`,
which write only the private handoff file.
"""

import difflib
import glob
import json
import os
import re
import stat
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

from ws import config
from ws.project import SLUG_PATTERN
from ws.userconfig import StandupConfig

GIT_TIMEOUT = 15
FIELD = "\x1f"
LOCAL_BRANCH_DAYS = 14
UNCOMMITTED_CAP = 10
HANDOFF_FILE = "HANDOFF-*.md"
CLOSED_MARK = "Status: encerrado"
HEAD_LINES = 10
HOOK_ERROR_DAYS = 7
PR_LIMIT = 50
PR_QUERY = (
    "query($q:String!){search(query:$q,type:ISSUE,first:50){issueCount nodes{"
    "... on PullRequest{number title url baseRefName headRefName isDraft reviewDecision "
    "updatedAt repository{name}}}}}"
)
TRACK = re.compile(r"ahead (\d+)|behind (\d+)|gone")


class HandoffError(Exception):
    """A handoff command refused or could not read what it was given."""


class _GitFailed(Exception):
    pass


def _tilde(path: Path | str) -> str:
    text = str(path)
    home = str(Path.home())
    if text == home:
        return "~"
    return "~" + text[len(home) :] if text.startswith(home + os.sep) else text


def _git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=GIT_TIMEOUT,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except subprocess.TimeoutExpired:
        raise _GitFailed(f"git {args[0]} timed out after {GIT_TIMEOUT} s") from None
    except OSError as error:
        raise _GitFailed(f"git {args[0]}: {error}") from None
    if result.returncode != 0:
        raise _GitFailed(f"git {args[0]} failed: {result.stderr.strip() or result.returncode}")
    return result.stdout


def _git_ok(repo: Path, *args: str) -> str | None:
    """The output, or None when git exits non-zero (an expected 'not set')."""
    try:
        return _git(repo, *args)
    except _GitFailed as error:
        if "timed out" in str(error):
            raise
        return None


def _is_repo(path: Path) -> bool:
    return not path.name.startswith(".") and path.is_dir() and (path / ".git").exists()


def _find_repos(cfg: StandupConfig, workspace: Path, warnings: list[str]) -> list[Path]:
    repos: dict[Path, Path] = {}
    for root in cfg.repo_roots:
        if not root.is_dir():
            warnings.append(f"repo root {_tilde(root)} does not exist")
            continue
        for child in sorted(root.iterdir(), key=lambda item: item.name):
            if _is_repo(child):
                repos[child.resolve()] = child
    if (workspace / ".git").exists():
        repos.setdefault(workspace.resolve(), workspace)
    return list(repos.values())


def _track(text: str) -> tuple[int, int, bool]:
    ahead = behind = 0
    gone = False
    for match in TRACK.finditer(text):
        if match.group(1):
            ahead = int(match.group(1))
        elif match.group(2):
            behind = int(match.group(2))
        else:
            gone = True
    return ahead, behind, gone


def _uncommitted(repo: Path) -> dict:
    out = _git(repo, "status", "--porcelain=v1", "-z")
    records = out.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4:
            continue
        paths.append(record[3:])
        if record[0] in "RC" or record[1] in "RC":
            index += 1
    return {
        "count": len(paths),
        "paths": paths[:UNCOMMITTED_CAP],
        "more": max(0, len(paths) - UNCOMMITTED_CAP),
    }


def _branch_table(repo: Path) -> dict[str, dict]:
    out = _git(
        repo,
        "for-each-ref",
        f"--format=%(refname:short){FIELD}%(upstream:short){FIELD}%(upstream:track){FIELD}"
        f"%(committerdate:unix){FIELD}%(committerdate:short)",
        "refs/heads",
    )
    table = {}
    for line in out.split("\n"):
        if not line:
            continue
        name, upstream, track, stamp, day = line.split(FIELD)
        ahead, behind, gone = _track(track)
        table[name] = {
            "upstream": upstream or None,
            "ahead": ahead,
            "behind": behind,
            "gone": gone,
            "stamp": int(stamp or 0),
            "day": day,
        }
    return table


def _parse_worktrees(out: str) -> list[dict]:
    blocks = []
    for chunk in out.split("\n\n"):
        entry: dict = {"locked": False, "prunable": False, "branch": None, "detached": False}
        for line in chunk.splitlines():
            key, _, value = line.partition(" ")
            if key == "worktree":
                entry["path"] = value
            elif key == "HEAD":
                entry["head"] = value[:7]
            elif key == "branch":
                entry["branch"] = value.removeprefix("refs/heads/")
            elif key == "detached":
                entry["detached"] = True
            elif key in ("locked", "prunable"):
                entry[key] = True
        if "path" in entry:
            blocks.append(entry)
    return blocks


def _ahead_of_default(repo: Path, default: str | None, branch: str) -> int | None:
    if default is None:
        return None
    for base in (f"origin/{default}", default):
        out = _git_ok(repo, "rev-list", "--count", f"{base}..{branch}")
        if out is not None:
            return int(out.strip())
    return None


def _worktrees(
    repo: Path, branches: dict[str, dict], main_branch: str | None, default: str | None
) -> tuple[list, set]:
    entries = _parse_worktrees(_git(repo, "worktree", "list", "--porcelain"))[1:]
    found = []
    checked_out = {main_branch} if main_branch else set()
    for entry in entries:
        branch = entry["branch"]
        info = branches.get(branch or "", {})
        if branch:
            checked_out.add(branch)
        state = None if entry["prunable"] else _uncommitted(Path(entry["path"]))["count"]
        ahead = info.get("ahead", 0)
        if branch and info and info["upstream"] is None:
            ahead = _ahead_of_default(repo, default, branch) or 0
        found.append(
            {
                "path": _tilde(entry["path"]),
                "branch": branch,
                "head": entry.get("head", ""),
                "uncommitted": state,
                "ahead": ahead,
                "behind": info.get("behind", 0),
                "locked": entry["locked"],
                "prunable": entry["prunable"],
            }
        )
    return found, checked_out


def _local_branches(
    repo: Path,
    branches: dict[str, dict],
    default: str | None,
    skip: set[str],
    now: datetime,
) -> list[dict]:
    since = (now - timedelta(days=LOCAL_BRANCH_DAYS)).timestamp()
    found = []
    for name, info in branches.items():
        if name in skip or name == default or info["stamp"] < since:
            continue
        if info["upstream"] is None:
            ahead = _ahead_of_default(repo, default, name)
            if ahead == 0:
                continue
        elif info["ahead"] > 0:
            ahead = info["ahead"]
        else:
            continue
        found.append(
            {
                "name": name,
                "ahead": ahead,
                "upstream": info["upstream"],
                "last_commit": info["day"],
            }
        )
    return sorted(found, key=lambda item: item["name"])


def _repo_state(repo: Path, now: datetime) -> dict:
    current = _git(repo, "branch", "--show-current").strip() or None
    detached = None if current else _git(repo, "rev-parse", "--short", "HEAD").strip()
    head_ref = _git_ok(repo, "symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD")
    default = head_ref.strip().removeprefix("origin/") if head_ref else None
    branches = _branch_table(repo)
    info = branches.get(current or "", {})
    worktrees, checked_out = _worktrees(repo, branches, current, default)
    stashes = len([line for line in _git(repo, "stash", "list").split("\n") if line])
    return {
        "name": repo.name,
        "path": _tilde(repo),
        "branch": current,
        "detached": detached,
        "default_branch": default,
        "upstream": info.get("upstream"),
        "ahead": info.get("ahead", 0),
        "behind": info.get("behind", 0),
        "gone": info.get("gone", False),
        "uncommitted": _uncommitted(repo),
        "stashes": stashes,
        "worktrees": worktrees,
        "local_branches": _local_branches(repo, branches, default, checked_out, now),
    }


def _has_something_to_say(state: dict) -> bool:
    default = state["default_branch"]
    off_default = state["detached"] is not None or (
        state["branch"] != default if default else state["branch"] not in ("main", "master")
    )
    return bool(
        off_default
        or state["ahead"]
        or state["behind"]
        or state["gone"]
        or state["uncommitted"]["count"]
        or state["stashes"]
        or state["worktrees"]
        or state["local_branches"]
    )


def _parse_prs(answer: str, warnings: list[str]) -> list[dict]:
    found = json.loads(answer)["data"]["search"]
    if found["issueCount"] > PR_LIMIT:
        warnings.append(f"gh: {found['issueCount']} open PRs found, only the first {PR_LIMIT} read")
    return [
        {
            "repo": node["repository"]["name"],
            "number": node["number"],
            "title": node["title"],
            "url": node["url"],
            "base": node["baseRefName"],
            "head": node["headRefName"],
            "draft": node["isDraft"],
            "review": node["reviewDecision"],
            "updated": node["updatedAt"],
        }
        for node in found["nodes"]
        if node
    ]


def _open_prs(gh: str, warnings: list[str]) -> list[dict]:
    try:
        result = subprocess.run(
            [gh, "api", "graphql", "-f", f"query={PR_QUERY}", "-f", "q=is:pr is:open author:@me"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=GIT_TIMEOUT * 2,
        )
        if result.returncode != 0:
            lines = result.stderr.strip().splitlines()
            raise RuntimeError(lines[0] if lines else f"exit {result.returncode}")
        return _parse_prs(result.stdout, warnings)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        warnings.append(f"gh: open PRs left out ({error or type(error).__name__})")
    except (ValueError, LookupError, TypeError, AttributeError) as error:
        warnings.append(f"gh: open PRs left out (unexpected answer: {type(error).__name__})")
    return []


def _hook_error_warning(now: datetime) -> str | None:
    log = config.cache_dir() / "hooks" / "errors.log"
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    since = now - timedelta(days=HOOK_ERROR_DAYS)
    counts: dict[str, int] = {}
    for line in lines:
        parts = line.split(" ", 2)
        if len(parts) < 3:
            continue
        try:
            stamp = datetime.fromisoformat(parts[0])
        except ValueError:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.astimezone()
        if stamp >= since:
            counts[parts[1]] = counts.get(parts[1], 0) + 1
    if not counts:
        return None
    detail = ", ".join(f"{name} {count}" for name, count in sorted(counts.items()))
    return (
        f"hooks: {sum(counts.values())} failure(s) in the last {HOOK_ERROR_DAYS} days "
        f"({detail}); see {_tilde(log)}"
    )


def _title_and_closed(path: Path) -> tuple[str, bool]:
    title = ""
    closed = False
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for _ in range(HEAD_LINES):
                line = handle.readline()
                if not line:
                    break
                if not title and line.startswith("# "):
                    title = line[2:].strip()
                if line.strip() == CLOSED_MARK:
                    closed = True
    except OSError:
        pass
    return title, closed


def find_handoffs(
    data_dir: Path,
    extra_globs: list[str],
    *,
    limit: int,
    max_age_days: int | None,
    now: datetime,
    include_closed: bool = False,
) -> list[dict]:
    """The newest handoff files: `<data>/projects/*/HANDOFF-*.md` and the extra globs."""
    patterns = [str(data_dir / "projects" / "*" / HANDOFF_FILE)]
    patterns += [os.path.expanduser(item) for item in extra_globs]
    seen: dict[str, float] = {}
    for pattern in patterns:
        for name in glob.glob(pattern):
            try:
                seen.setdefault(name, os.stat(name).st_mtime)
            except OSError:
                continue
    oldest = None if max_age_days is None else (now - timedelta(days=max_age_days)).timestamp()
    found = []
    for name, mtime in sorted(seen.items(), key=lambda item: item[1], reverse=True):
        if oldest is not None and mtime < oldest:
            continue
        path = Path(name)
        title, closed = _title_and_closed(path)
        if closed and not include_closed:
            continue
        found.append(
            {
                "path": _tilde(path),
                "project": path.parent.name,
                "modified": datetime.fromtimestamp(mtime, now.tzinfo).isoformat(timespec="seconds"),
                "title": title,
                "closed": closed,
            }
        )
        if len(found) == limit:
            break
    return found


def collect(
    cfg: StandupConfig,
    workspace: Path,
    *,
    include_clean: bool = False,
    prs: bool = True,
    gh: str = "gh",
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now().astimezone()
    warnings: list[str] = []
    repos: list[dict] = []
    clean = 0
    for repo in _find_repos(cfg, workspace, warnings):
        try:
            state = _repo_state(repo, now)
        except _GitFailed as error:
            warnings.append(f"repo {repo.name}: left out ({error})")
            continue
        if include_clean or _has_something_to_say(state):
            repos.append(state)
        else:
            clean += 1
    hook_warning = _hook_error_warning(now)
    if hook_warning:
        warnings.append(hook_warning)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "fetched": False,
        "repos": repos,
        "clean_repos": clean,
        "prs": _open_prs(gh, warnings) if prs else [],
        "handoffs": find_handoffs(
            config.data_dir(),
            _extra_globs(),
            limit=5,
            max_age_days=None,
            now=now,
            include_closed=True,
        ),
        "warnings": warnings,
    }


def _extra_globs() -> list[str]:
    """`[handoff] extra_globs` of config.toml; a missing or invalid table means none."""
    from ws import userconfig

    try:
        value = userconfig.load_table("handoff").get("extra_globs", [])
    except (userconfig.ConfigMissing, userconfig.ConfigInvalid):
        return []
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return []


STATE_BEGIN = "<!-- ws:state:begin: gerado por ws handoff; para atualizar, ws handoff refresh -->"
STATE_END = "<!-- ws:state:end -->"
STATE_BLOCK = re.compile(
    r"^<!-- ws:state:begin[^\n]*-->\n(?:.*?\n)?<!-- ws:state:end -->", re.MULTILINE | re.DOTALL
)
TOPIC = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
MAX_TOPIC = 40
FILE_NAME = re.compile(r"HANDOFF-\d{8}-[a-z0-9]+(-[a-z0-9]+)*\.md")
TITLE = re.compile(r"# Handoff \d{2}/\d{2}/\d{4}: \S")
FRONT = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)
NEXT_STEPS = "**Próximos passos:**"
RESUME_HEADING = "## Ordem sugerida ao retomar"
RESUME_DEFAULT = "1. Ler este arquivo inteiro."
TMP_PATH = re.compile(r"(?<![\w./~-])/tmp/")
LONG_FILE_LINES = 300
PLACEHOLDERS = (
    "tema em poucas palavras",
    "Por que o chat parou",
    "Frente",
    "o que está pronto",
    "decisões desta sessão",
    "o que ficou de fora",
    "ação concreta",
    "worktree, branch, último commit",
    "o que só ele pode fazer",
)


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split()).replace("|", "\\|").replace("<!--", "&lt;!--")


def _table(header: list[str], rows: list[list[object]]) -> list[str]:
    lines = [f"| {' | '.join(header)} |", f"|{'|'.join(' --- ' for _ in header)}|"]
    lines += [f"| {' | '.join(_cell(value) for value in row)} |" for row in rows]
    return lines


def _paths_cell(uncommitted: dict | None) -> str:
    if not uncommitted or not uncommitted["count"]:
        return "0"
    shown = ", ".join(uncommitted["paths"])
    more = f", +{uncommitted['more']}" if uncommitted["more"] else ""
    return f"{uncommitted['count']}: {shown}{more}"


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def render_state(collected: dict) -> str:
    """The marked state block of the handoff file, in Markdown tables."""
    lines = [STATE_BEGIN, f"Gerado em {collected['generated_at']}.", ""]
    repos = collected["repos"]
    if repos:
        rows = []
        for repo in repos:
            branch = repo["branch"] or f"(detached {repo['detached']})"
            upstream = repo["upstream"] or ""
            if repo["gone"]:
                upstream = f"{upstream} (removido no remoto)"
            rows.append(
                [
                    repo["name"],
                    branch,
                    upstream,
                    repo["ahead"],
                    repo["behind"],
                    _paths_cell(repo["uncommitted"]),
                    repo["stashes"],
                ]
            )
        header = [
            "Repositório",
            "Branch",
            "Upstream",
            "À frente",
            "Atrás",
            "Não commitados",
            "Stash",
        ]
        lines += ["### Repositórios", "", *_table(header, rows), ""]
    else:
        lines += ["Nenhum repositório com pendências.", ""]
    worktrees = [
        [
            repo["name"],
            tree["path"],
            tree["branch"] or "(detached)",
            tree["head"],
            "?" if tree["uncommitted"] is None else tree["uncommitted"],
            tree["ahead"],
            tree["behind"],
            ", ".join(
                label
                for flag, label in ((tree["locked"], "travada"), (tree["prunable"], "removível"))
                if flag
            ),
        ]
        for repo in repos
        for tree in repo["worktrees"]
    ]
    if worktrees:
        header = [
            "Repositório",
            "Caminho",
            "Branch",
            "Head",
            "Não commitados",
            "À frente",
            "Atrás",
            "Obs",
        ]
        lines += ["### Worktrees", "", *_table(header, worktrees), ""]
    branches = [
        [repo["name"], item["name"], item["ahead"], item["upstream"], item["last_commit"]]
        for repo in repos
        for item in repo["local_branches"]
    ]
    if branches:
        header = ["Repositório", "Branch só local", "À frente", "Upstream", "Último commit"]
        lines += ["### Branches só locais (14 dias)", "", *_table(header, branches), ""]
    if collected["prs"]:
        rows = [
            [
                pr["repo"],
                f"[#{pr['number']}]({pr['url']})",
                pr["title"],
                f"{pr['head']} → {pr['base']}",
                "rascunho" if pr["draft"] else (pr["review"] or "sem revisão"),
            ]
            for pr in collected["prs"]
        ]
        header = ["Repositório", "PR", "Título", "Branch", "Revisão"]
        lines += ["### PRs abertos", "", *_table(header, rows), ""]
    if collected["warnings"]:
        lines += ["### Avisos da coleta", "", *(f"- {_cell(w)}" for w in collected["warnings"]), ""]
    footer = "Contagem à frente/atrás pelo último fetch"
    clean = collected["clean_repos"]
    if clean:
        footer += f"; {_plural(clean, 'repositório limpo omitido', 'repositórios limpos omitidos')}"
    lines += [f"{footer}.", STATE_END]
    return "\n".join(lines)


def _replace_state(text: str, block: str) -> str:
    if not STATE_BLOCK.search(text):
        raise HandoffError("the state block markers were not found in the file")
    return STATE_BLOCK.sub(lambda _: block, text, count=1)


def new_handoff(
    slug: str, topic: str, day: date, collected: dict, *, root: Path, data_dir: Path
) -> Path:
    """Creates `HANDOFF-YYYYMMDD-<topic>.md` (mode 600) in the project's private folder (700)."""
    if not SLUG_PATTERN.fullmatch(slug):
        raise HandoffError(f"invalid slug {slug!r}: lowercase letters, digits and hyphens")
    if not (root / "projects" / slug).is_dir():
        raise HandoffError(f"unknown project {slug!r}: there is no projects/{slug} folder")
    if len(topic) > MAX_TOPIC or not TOPIC.fullmatch(topic):
        raise HandoffError(
            f"invalid topic {topic!r}: lowercase words joined by single hyphens, "
            f"at most {MAX_TOPIC} characters"
        )
    folder = data_dir / "projects" / slug
    target = folder / f"HANDOFF-{day.strftime('%Y%m%d')}-{topic}.md"
    if target.exists():
        raise HandoffError(f"already exists: {target.name}; write another topic or edit it")
    try:
        template = (root / "templates" / "handoff.md").read_text(encoding="utf-8")
    except OSError as error:
        raise HandoffError(f"cannot read the template: {error}") from None
    filled = template.replace("{{data}}", day.strftime("%d/%m/%Y"))
    text = _replace_state(filled, render_state(collected))
    if not folder.exists():
        folder.mkdir(parents=True)
        folder.chmod(0o700)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
    target.chmod(0o600)
    return target


def _without_stamp(block: str) -> list[str]:
    return [line for line in block.splitlines() if not line.startswith("Gerado em ")]


def refresh(path: Path, collected: dict, *, diff_only: bool) -> str:
    """Re-renders the marked block only and returns its diff, the stamp line aside."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise HandoffError(f"cannot read {path}: {error}") from None
    match = STATE_BLOCK.search(text)
    if not match:
        raise HandoffError(f"the state block markers were not found in {path.name}")
    block = render_state(collected)
    diff = difflib.unified_diff(
        _without_stamp(match.group(0)), _without_stamp(block), lineterm="", n=0
    )
    if not diff_only:
        path.write_text(_replace_state(text, block), encoding="utf-8")
    return "\n".join(line for line in list(diff)[2:] if not line.startswith("@@"))


def _section(text: str, heading: str) -> str | None:
    match = re.search(rf"^{re.escape(heading)}[ \t]*$", text, re.MULTILINE)
    if not match:
        return None
    rest = text[match.end() :]
    following = re.search(r"^## ", rest, re.MULTILINE)
    return rest[: following.start()] if following else rest


def _front_problems(text: str) -> list[str]:
    fronts = list(FRONT.finditer(text))
    if not fronts:
        return ["no front section (## N. <frente>)"]
    problems = []
    for front in fronts:
        body = text[front.end() :]
        following = re.search(r"^## ", body, re.MULTILINE)
        if following:
            body = body[: following.start()]
        if not _next_steps_filled(body):
            problems.append(f"front '{front.group(2)}' has no filled {NEXT_STEPS}")
    return problems


def _next_steps_filled(body: str) -> bool:
    if NEXT_STEPS not in body:
        return False
    content = []
    for line in body.split(NEXT_STEPS, 1)[1].splitlines():
        if re.match(r"\*\*[^*]+:\*\*", line):
            break
        content.append(line)
    text = "\n".join(content)
    if any(f"<{known}" in text for known in PLACEHOLDERS):
        return False
    return bool(re.sub(r"[\s\d.\-*]", "", text))


def _allowed_place(path: Path, data_dir: Path, extra_globs: list[str]) -> bool:
    resolved = path.resolve()
    if resolved.parent.parent == (data_dir / "projects").resolve():
        return True
    for pattern in extra_globs:
        if any(Path(name).resolve() == resolved for name in glob.glob(os.path.expanduser(pattern))):
            return True
    return False


def check(path: Path, *, data_dir: Path, extra_globs: list[str]) -> dict:
    """The verdict on a handoff file: `ok`, `problems` (block) and `warnings` (do not)."""
    try:
        text = path.read_text(encoding="utf-8")
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as error:
        raise HandoffError(f"cannot read {path}: {error}") from None
    problems: list[str] = []
    warnings: list[str] = []
    if not _allowed_place(path, data_dir, extra_globs):
        problems.append(
            "the file is outside the private project folders and the extra_globs folders"
        )
    if not FILE_NAME.fullmatch(path.name):
        problems.append(f"the name {path.name!r} does not match HANDOFF-YYYYMMDD-<topic>.md")
    if mode != 0o600:
        problems.append(f"the mode is {mode:o}, expected 600")
    if not TITLE.match(text.split("\n", 1)[0]):
        problems.append("the first line is not a title '# Handoff DD/MM/AAAA: <tema>'")
    problems += _front_problems(text)
    if not STATE_BLOCK.search(text):
        problems.append("the state block (ws:state markers) is missing; run ws handoff refresh")
    resume = _section(text, RESUME_HEADING)
    filled = [
        line
        for line in (resume or "").splitlines()
        if line.strip() and line.strip() != RESUME_DEFAULT
    ]
    if resume is None:
        problems.append(f"the section '{RESUME_HEADING}' is missing")
    elif not filled:
        problems.append(f"the section '{RESUME_HEADING}' is empty")
    outside_block = STATE_BLOCK.sub("", text)
    if any(f"<{known}" in outside_block for known in PLACEHOLDERS):
        problems.append("a template placeholder is still in the file (text between < and >)")
    lines = len(text.splitlines())
    if lines > LONG_FILE_LINES:
        warnings.append(f"the file has {lines} lines, over {LONG_FILE_LINES}: cut what is history")
    if TMP_PATH.search(outside_block):
        warnings.append("a path under /tmp/ is cited; it is gone after a shutdown of the WSL")
    return {"ok": not problems, "path": _tilde(path), "problems": problems, "warnings": warnings}
