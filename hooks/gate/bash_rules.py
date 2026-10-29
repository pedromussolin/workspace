"""The approval gate's rules for Bash: which commands write outside the machine, and the box text.

`decide(command, cwd)` splits the command with `shell.scan` (so `bash -c`, `eval`, `$(...)` and
heredocs are looked at) and returns one decision. Families, each with its own PT-BR box: `git
push` (and what redirects it), `gh`, `curl`/`wget`, `ws card apply`, the protection of the Claude
Code settings and hooks, and commands the gate cannot read with certainty. Everything else passes.

"Unquoted" for the obfuscation rule: an expansion that the shell does not keep as one literal
argument, that is a `$`, a backtick or a brace expansion (`{a,b}`, `{1..3}`) outside every quote.
`shell.Word.bare` carries it, from a parser that tracks quotes itself, because `shlex` drops them.
A `$(...)` inside double quotes (`git commit -m "$(cat <<'EOF' ...)"`) is one argument whatever it
prints, so it is not obfuscation; only a double-quoted expansion standing in the subcommand
(`git "$x"`) is, since there it picks the verb.

What the rule covers depends on the program. `curl`, `wget` and `ws`: any unquoted expansion in
the arguments. `git` and `gh`: only the program word and the subcommand words (`git`: the first
word after the global options and their values; `gh`: the two words after `-R/--repo VALUE`),
because a read verb with an expanded argument (`git log main..$B`) cannot become a write, while
the write families (`push`, `remote`, `config` of the push destination, `gh` writes) judge their
own arguments. `gh api` also asks for a word that starts with an expansion or a dash and is not
the endpoint (`$FLAGS`, `-X$M`, `-X $M`), since it could inject a method or fields.

Text rules cannot see a script file the command runs, text piped to `python` or `node`, programs
that start other programs (`xargs`, `find -exec`, `ssh`) or a `cwd` that Claude Code reports stale.
The push box runs three local, read-only `git` queries to name the branch (see `_branch_state`).

A plain `git push` (or `git push origin main`) shows no box only when all of these hold, in
`[gate]` of `~/.config/workspace/config.toml`: the cwd is listed in `push_without_asking`; every
push URL of `origin` (`git remote get-url --push --all origin`) is listed in `push_remotes`; a
bare `git push` is not sent to another remote by `branch.*.pushRemote`, `remote.pushDefault` or
`branch.*.remote`; and the repository's local config sets none of the keys that run a program or
redirect the push (`LOCAL_RISKY_KEYS`; `core.hooksPath` only as `.githooks`). `.git/config` can
change outside the gate (the Edit tool is not in its matcher), so these are read from git at each
push, with the repository's `fsmonitor` and hooks off. A missing list, a mismatch or a failed
query asks, and the box shows the real push URL and the names (never the values) of the keys.
"""

import fnmatch
import json
import os
import re
import subprocess
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from . import shell
from .decision import PASS, Decision, ask, body_summary, cut, deny
from .shell import Command, Scan, Word, program_name

TITLE_GITHUB = "Gravar fora — GitHub"
TITLE_JIRA = "Gravar fora — Jira"
TITLE_HTTP = "Gravar fora — HTTP"
TITLE_PROTECTION = "Proteção do Claude Code"
TITLE_UNSURE = "Comando não lido com certeza"
TITLE_REMOTE = "Destino do git push"
TITLE_CREDENTIAL = "Lê uma credencial"

WATCHED = {"git", "gh", "curl", "wget", "ws"}
NAMES = re.compile(r"\b(?:ws|gh|git|curl|wget)\b")
APPROVE_CODE = re.compile(r"[0-9a-f]{12}")
WS_BY_CODE = re.compile(r"\bfrom\s+ws\b|\bimport\s+ws\b|\bws\.card\b|run_apply")
GIT_DIRECTORY_VARIABLE = re.compile(r"GIT_(?:DIR|WORK_TREE|COMMON_DIR|INDEX_FILE)=")

CATCH_ALL_HARMLESS = set("echo printf grep rg cat head tail ls wc test [ which type".split())
READ_ONLY = {"cat", "head", "tail", "less", "ls", "stat", "sha256sum", "diff", "grep", "rg", "jq"}
READ_ONLY_GIT = {"add", "diff", "log", "show", "status", "blame", "ls-files", "grep"}
NAVIGATION = {"cd", "pushd", "popd"}
HARMLESS = READ_ONLY | NAVIGATION | {"echo", "printf", "true", "false", "pwd", "test", "["}
INTERPRETERS = re.compile(r"python[0-9.]*|node(?:js)?|perl|ruby|deno|php|lua")
PROTECTED_PATH = re.compile(
    r"(?:^|/)(?:\.claude(?:/(?:hooks(?:/|$)|settings[^/]*$|[^/]*[*?\[][^/]*$)|/?$)"
    r"|\.githooks(?:/|$)|\.git/(?:config|hooks)(?:/|$))"
)
PROTECTED_IN_CODE = re.compile(r"\.claude/(?:hooks|settings)|\.githooks|\.git/(?:config|hooks)")
PROTECTED_DIRECTORY = re.compile(r"(?:^|/)(?:\.claude(?:/hooks)?|\.githooks)/?$")

CREDENTIAL_FILE = re.compile(r"(?:^|/)\.config/(?:workspace/credentials|gh/hosts\.yml)$")
CREDENTIAL_FOLDER = re.compile(r"(?:^|/)(?:\.config/workspace|\.config/gh|\.ssh)/?$")
CREDENTIAL_GLOB = re.compile(r"(?:^|/)(\.config/workspace|\.config/gh|\.ssh)/([^/]*[*?\[][^/]*)$")
SSH_PRIVATE_KEY = re.compile(r"(?:^|/)\.ssh/id_[^/]*$")
CREDENTIAL_IN_CODE = re.compile(
    r"\.config/workspace/credentials|\.config/gh/hosts\.yml|\.ssh/id_[\w.-]*"
)
CREDENTIAL_SAMPLES = {
    ".config/workspace": ("credentials",),
    ".config/gh": ("hosts.yml",),
    ".ssh": ("id_ed25519", "id_rsa", "id_ecdsa", "id_dsa"),
}
CREDENTIAL_TARGETS = (
    "~/.config/workspace/credentials",
    "~/.config/gh/hosts.yml",
    "~/.ssh/id_rsa",
    "~/.ssh/id_ed25519",
    "~/.ssh/id_ecdsa",
    "~/.ssh/id_dsa",
    "~/.config/workspace",
    "~/.config/gh",
    "~/.ssh",
)
PARENT_TARGETS = ("~", "~/.config")
PARENT_FOLDER = re.compile(r"(?:^|/)\.config/?$|^(?:~|\$HOME|\$\{HOME\})/?$")
CODE_HOME = re.compile(r"Path\.home\(\)|expanduser\(|environ\b.{0,4}HOME|getenv\(\s*.HOME")
CODE_CREDENTIAL_NAME = re.compile(r"credentials|hosts\.yml|\.ssh\b")
RECURSIVE_PROGRAMS = {"rg", "tar", "bsdtar", "zip", "7z", "rsync"}
RECURSIVE_FLAGS = {
    "grep": ("rR", ("--recursive", "--dereference-recursive")),
    "egrep": ("rR", ("--recursive", "--dereference-recursive")),
    "fgrep": ("rR", ("--recursive", "--dereference-recursive")),
    "cp": ("rRa", ("--recursive", "--archive")),
    "scp": ("r", ()),
}
FIND_RUNS = {"-exec", "-execdir", "-ok", "-okdir"}
METADATA_PROGRAMS = {"ls", "stat"}
TEST_PROGRAMS = {"test", "[", "[["}
TEST_METADATA_FLAGS = {"-e", "-f", "-d", "-s", "-r", "-w", "-x", "-L", "-h"}

GIT_VALUE_OPTIONS = {
    "-C",
    "-c",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--super-prefix",
    "--config-env",
}
REMOTE_KEY_STARTS = ("remote.", "url.", "alias.", "branch.", "core.sshcommand")
RISKY_GIT_KEYS = re.compile(
    r"^(?:alias\.|credential\.|remote\.|url\.|pager\.|filter\.|include\.path$|includeif\."
    r"|core\.(?:pager|sshcommand|editor"
    r"|fsmonitor|askpass|gitproxy|hookspath)$|sequence\.editor$|diff\.external$|gpg\.program$"
    r"|.*\.command$|.*\.textconv$)"
)
STORE_VARIABLE = re.compile(r"(?:WS_[A-Za-z0-9_]*|HOME)(?:=|$)")
STORE_PROGRAMS = {"env", "sudo"}
PUSH_URL = re.compile(r"^(?:[a-z][a-z0-9+.-]*://|[^/:]+@[^/:]+:|[^/:]{2,}:|/|\.\.?/|~)", re.I)
LOCAL_RISKY_KEYS = (
    r"^(core\.(sshcommand|askpass|hookspath)|credential\..*"
    r"|remote\..*\.(receivepack|uploadpack|proxy|vcs)|url\..*\.(insteadof|pushinsteadof)"
    r"|http\..*proxy.*|include\.path|includeif\..*)$"
)
GIT_CONFIG_VARIABLE = re.compile(r"GIT_CONFIG[A-Z0-9_]*=")
QUIET_FLAGS = ("-q", "--quiet")
INJECTING_START = "$`{-"
BRANCH_QUERY_TIMEOUT = 3.0
PUSH_VALUE_FLAGS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
FORCE_FLAGS = ("-f", "--force", "--force-with-lease", "--force-if-includes")
REMOTE_CHANGES = {"add", "set-url", "rename", "remove", "rm", "set-head", "set-branches"}
CONFIG_READS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l"}
REMOTE_KEYS = re.compile(
    r"(?i)^(?:remote\.|url\.|alias\.|branch\.[^.]+\.(?:remote|pushremote)$|core\.sshcommand$)"
)

GH_READS = {
    "pr": {"view", "list", "diff", "checks", "status"},
    "issue": {"view", "list", "status"},
    "repo": {"view", "list", "clone"},
    "run": {"view", "list", "watch"},
    "release": {"view", "list", "download"},
    "auth": {"status"},
}
GH_ANY_ACTION = {"search", "help", "version"}
GH_GLOBAL_VALUES = {"-R", "--repo", "--hostname"}
GH_API_VALUES = GH_GLOBAL_VALUES | {
    "-X",
    "--method",
    "-f",
    "-F",
    "--field",
    "--raw-field",
    "--input",
    "-H",
    "--header",
    "-q",
    "--jq",
    "-t",
    "--template",
    "--cache",
    "-p",
    "--preview",
}
GH_API_FIELDS = {"-f", "-F", "--field", "--raw-field", "--input"}
GH_CHANGE_VALUES = GH_GLOBAL_VALUES | {
    "-B",
    "--base",
    "-H",
    "--head",
    "-t",
    "--title",
    "-b",
    "--body",
    "-F",
    "--body-file",
    "-a",
    "--assignee",
    "-l",
    "--label",
    "-m",
    "--milestone",
    "-r",
    "--reviewer",
    "-p",
    "--project",
    "-c",
    "--comment",
}
GH_MERGE_VALUES = GH_GLOBAL_VALUES | {"-t", "--subject", "-b", "--body", "-F", "--body-file"}
GH_MERGE_METHODS = {"-m": "merge", "--merge": "merge", "-s": "squash", "--squash": "squash"}
GH_MERGE_METHODS |= {"-r": "rebase", "--rebase": "rebase"}
GH_CALLED_OUT = ("--admin", "--force", "--delete-branch")

CURL_VALUE_FLAGS = {
    "-A",
    "-b",
    "-c",
    "-C",
    "-d",
    "-D",
    "-e",
    "-E",
    "-F",
    "-H",
    "-K",
    "-m",
    "-o",
    "-P",
    "-r",
    "-T",
    "-u",
    "-U",
    "-w",
    "-x",
    "-X",
    "-y",
    "-Y",
    "-z",
    "--request",
    "--data",
    "--data-raw",
    "--data-binary",
    "--data-ascii",
    "--data-urlencode",
    "--form",
    "--form-string",
    "--header",
    "--output",
    "--output-dir",
    "--user",
    "--user-agent",
    "--referer",
    "--cookie",
    "--cookie-jar",
    "--upload-file",
    "--url",
    "--json",
    "--max-time",
    "--connect-timeout",
    "--retry",
    "--retry-delay",
    "--retry-max-time",
    "--proxy",
    "--proxy-user",
    "--cacert",
    "--cert",
    "--key",
    "--resolve",
    "--range",
    "--write-out",
    "--config",
    "--dump-header",
    "--time-cond",
    "--oauth2-bearer",
    "--interface",
    "--limit-rate",
    "--continue-at",
    "--expand-data",
    "--expand-json",
    "--expand-form",
}
CURL_DATA = re.compile(r"^--(?:data|form|json|upload-file|expand-(?:data|json|form))")
CURL_DATA_SHORT = {"-d", "-F", "-T"}
WGET_VALUE_FLAGS = {
    "--method",
    "--post-data",
    "--post-file",
    "--body-data",
    "--body-file",
    "--header",
    "--output-document",
    "--output-file",
    "--directory-prefix",
    "--user",
    "--password",
    "--user-agent",
    "--referer",
    "--load-cookies",
    "--save-cookies",
    "-O",
    "-o",
    "-a",
    "-P",
    "-e",
    "-t",
    "-T",
    "-w",
    "-U",
    "-i",
    "-B",
}
WGET_DATA = re.compile(r"^--(?:post-|body-)")
SAFE_METHODS = {"GET", "HEAD"}


@dataclass(frozen=True)
class Finding:
    """What one command asks for; a `denial` (English, for the model) blocks the call instead."""

    title: str
    lines: tuple[str, ...]
    denial: str = ""
    brief: str = ""
    alert: bool = False

    def compact(self) -> str:
        """Its one line in a box shared with other findings: destination first."""
        text = self.brief or (self.lines[0] if self.lines else self.title)
        text = text.removeprefix("ATENÇÃO: ")
        alert = self.alert or self.title in (TITLE_UNSURE, TITLE_CREDENTIAL)
        return f"ATENÇÃO: {text}" if alert else text


@dataclass
class Parsed:
    positionals: list[Word]
    positions: list[int]
    flags: list[tuple[str, str | None]]

    def has(self, *names: str) -> bool:
        return any(name in names for name, _ in self.flags)

    def value(self, *names: str) -> str | None:
        found = [value for name, value in self.flags if name in names and value is not None]
        return found[-1] if found else None

    def values(self, *names: str) -> list[str]:
        return [value for name, value in self.flags if name in names and value is not None]


def parse_flags(words: list[Word], value_flags: set[str]) -> Parsed:
    """Split arguments into positionals and flags; short groups (`-sSf`, `-XPOST`) are opened."""
    parsed = Parsed([], [], [])
    index = 0
    while index < len(words):
        text = words[index].text
        position = index
        index += 1
        if text == "--":
            for rest in range(index, len(words)):
                parsed.positionals.append(words[rest])
                parsed.positions.append(rest)
            break
        if text.startswith("--"):
            name, equals, value = text.partition("=")
            if equals:
                parsed.flags.append((name, value))
            elif name in value_flags and index < len(words):
                parsed.flags.append((name, words[index].text))
                index += 1
            else:
                parsed.flags.append((name, None))
        elif text.startswith("-") and len(text) > 1:
            letters = text[1:]
            for offset, letter in enumerate(letters):
                flag = "-" + letter
                if flag not in value_flags:
                    parsed.flags.append((flag, None))
                    continue
                rest = letters[offset + 1 :]
                if rest:
                    parsed.flags.append((flag, rest))
                elif index < len(words):
                    parsed.flags.append((flag, words[index].text))
                    index += 1
                else:
                    parsed.flags.append((flag, None))
                break
        else:
            parsed.positionals.append(words[position])
            parsed.positions.append(position)
    return parsed


def _pretty(path: str) -> str:
    home = str(Path.home())
    return "~" + path[len(home) :] if path == home or path.startswith(home + "/") else path


def _line(command: Command | list[str], width: int = 110) -> str:
    texts = command if isinstance(command, list) else [word.text for word in command.words]
    return "Comando: " + cut(" ".join(texts), width)


def _unsure(texts: list[str], reason: str) -> Finding:
    brief = f"Não lido com certeza: {reason.removeprefix('ATENÇÃO: ')} ({cut(' '.join(texts), 60)})"
    return Finding(
        TITLE_UNSURE,
        (reason, _line(texts), "Confira o comando antes de aprovar."),
        brief=brief,
    )


def _config_dir() -> Path:
    return Path(os.environ.get("WS_CONFIG_DIR") or Path.home() / ".config" / "workspace")


def _data_dir() -> Path:
    return Path(os.environ.get("WS_DATA_DIR") or Path.home() / ".local" / "share" / "workspace")


def _listed_for_push(cwd: str) -> bool:
    if not cwd:
        return False
    try:
        with open(_config_dir() / "config.toml", "rb") as handle:
            listed = tomllib.load(handle)["gate"]["push_without_asking"]
        here = os.path.realpath(cwd)
        return any(
            isinstance(path, str) and os.path.realpath(os.path.expanduser(path)) == here
            for path in listed
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _runs_cd(scan: Scan) -> bool:
    return any(
        name in NAVIGATION
        for command in scan.commands
        for name, _ in shell.invocations(command)[:1]
    )


def _changes_directory(scan: Scan) -> bool:
    """Whether anything in the command line could make a push run in another folder."""
    if _runs_cd(scan):
        return True
    for command in scan.commands:
        for word in command.words:
            text = word.text
            if text == "-C" or text.startswith(("--git-dir", "--work-tree")):
                return True
            if GIT_DIRECTORY_VARIABLE.match(text):
                return True
    return False


def _split_git(args: list[Word]) -> tuple[list[Word], int | None]:
    """The `-C` directories and the index of the subcommand among the arguments."""
    directories: list[Word] = []
    index = 0
    while index < len(args) and args[index].text.startswith("-"):
        option = args[index].text
        index += 1
        if option in GIT_VALUE_OPTIONS and index < len(args):
            if option == "-C":
                directories.append(args[index])
            index += 1
    return directories, index if index < len(args) else None


def _git_overrides(args: list[Word]) -> list[str]:
    """The `-c` and `--config-env` settings among git's global options, as typed."""
    found: list[str] = []
    index = 0
    while index < len(args) and args[index].text.startswith("-"):
        option = args[index].text
        index += 1
        if option.startswith("--config-env="):
            found.append(option)
        elif option in GIT_VALUE_OPTIONS and index < len(args):
            if option in ("-c", "--config-env"):
                found.append(f"{option} {args[index].text}")
            index += 1
    return found


def _override_key(override: str) -> str:
    setting = override.split(" ", 1)[1] if " " in override else override.partition("=")[2]
    return setting.partition("=")[0].lower()


def _risky_overrides(overrides: list[str]) -> list[str]:
    return [override for override in overrides if RISKY_GIT_KEYS.match(_override_key(override))]


def _redirects_push(override: str) -> bool:
    return _override_key(override).startswith(("remote.", "url.", "alias.", "core.sshcommand"))


def _folder(cwd: str, directories: list[Word]) -> str:
    folder = cwd or "."
    for directory in directories:
        folder = os.path.normpath(os.path.join(folder, os.path.expanduser(directory.text)))
    return folder


def _in_repository(folder: str) -> bool:
    path = Path(folder)
    return path.is_dir() and any((each / ".git").exists() for each in (path, *path.parents))


def _local_git(
    folder: str, query: list[str], deadline: float
) -> subprocess.CompletedProcess[str] | None:
    """One local, read-only `git` query with the repository's `fsmonitor` and hooks switched off.

    A hostile `.git/config` must not run code from the gate. None on any failure or timeout.
    """
    left = deadline - time.monotonic()
    if left <= 0:
        return None
    environment = {name: os.environ[name] for name in ("PATH", "HOME") if name in os.environ}
    environment |= {"LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
    base = ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null"]
    try:
        return subprocess.run(
            [*base, *query],
            cwd=folder,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=left,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _push_destination(folder: str, bare: bool) -> tuple[list[str], str | None] | None:
    """The push URLs of `origin` and, for a bare `git push`, a setting that sends it elsewhere.

    `.git/config` can change without the gate seeing it (the Edit tool is outside its matcher),
    so the no-box push checks where it really goes. None when git cannot tell.
    """
    if not _in_repository(folder):
        return None
    deadline = time.monotonic() + BRANCH_QUERY_TIMEOUT
    elsewhere = None
    if bare:
        pattern = r"^(branch\..*\.(pushremote|remote)|remote\.pushdefault)$"
        done = _local_git(folder, ["config", "--get-regexp", pattern], deadline)
        if done is None or done.returncode not in (0, 1):
            return None
        for line in done.stdout.splitlines():
            key, _, value = line.partition(" ")
            if value != "origin":
                elsewhere = f"{key}={value}"
                break
    done = _local_git(folder, ["remote", "get-url", "--push", "--all", "origin"], deadline)
    if done is None or done.returncode != 0:
        return None
    urls = [line.strip() for line in done.stdout.splitlines() if line.strip()]
    return (urls, elsewhere) if urls else None


def _local_risky_keys(folder: str) -> list[str] | None:
    """Keys of the repository's local config that run a program or redirect a push; None if
    git cannot tell. Only the names leave this function: a value may hold a secret."""
    deadline = time.monotonic() + BRANCH_QUERY_TIMEOUT
    done = _local_git(folder, ["config", "--local", "--get-regexp", LOCAL_RISKY_KEYS], deadline)
    if done is None or done.returncode not in (0, 1):
        return None
    keys = []
    for line in done.stdout.splitlines():
        key, _, value = line.partition(" ")
        if key == "core.hookspath" and value.strip() == ".githooks":
            continue
        if key and key not in keys:
            keys.append(key)
    return keys


def _allowed_push_remotes() -> set[str]:
    try:
        with open(_config_dir() / "config.toml", "rb") as handle:
            listed = tomllib.load(handle)["gate"]["push_remotes"]
        return {url for url in listed if isinstance(url, str)}
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def _branch_state(folder: str) -> tuple[str, str, int] | None:
    """The current branch, its upstream and how many commits it is ahead, or None.

    Three local queries, no network, with the repository's own `fsmonitor` and hooks switched off
    (a hostile `.git/config` must not run code from the gate) and a shared deadline. Any failure,
    a branch without upstream and a detached HEAD included, gives None.
    """
    if not _in_repository(folder):
        return None
    queries = (
        ["rev-parse", "--abbrev-ref", "HEAD"],
        ["rev-parse", "--abbrev-ref", "@{u}"],
        ["rev-list", "--count", "@{u}..HEAD"],
    )
    deadline = time.monotonic() + BRANCH_QUERY_TIMEOUT
    answers: list[str] = []
    for query in queries:
        done = _local_git(folder, query, deadline)
        answer = done.stdout.strip() if done else ""
        if done is None or done.returncode != 0 or not answer or "\n" in answer:
            return None
        answers.append(answer)
    branch, upstream, ahead = answers
    if branch == "HEAD" or not ahead.isdigit():
        return None
    return branch, upstream, int(ahead)


def _push(
    rest: list[Word],
    directories: list[Word],
    cwd: str,
    moved: bool,
    overrides: list[str],
    destination: tuple[list[str], str | None] | None = None,
    warnings: list[str] | None = None,
) -> Finding:
    parsed = parse_flags(rest, PUSH_VALUE_FLAGS)
    names = [word.text for word in parsed.positionals]
    remote = parsed.value("--repo")
    if remote is None and names:
        remote, names = names[0], names[1:]
    forced = [name for name, _ in parsed.flags if name.startswith(FORCE_FLAGS)]
    forced += ["+" + spec[1:] for spec in names if spec.startswith("+")]
    deleted = parsed.has("--delete", "-d") or any(spec.startswith(":") for spec in names)
    folder = _folder(cwd, directories)
    redirecting = [override for override in overrides if _redirects_push(override)]
    state = None
    if not names and not moved and not any(word.expands for word in directories):
        state = _branch_state(folder)
    if redirecting:
        shown = f"{remote or 'o padrão'}, mudado por {redirecting[0]}"
    else:
        shown = remote or "o padrão do repositório"
    lines = [
        f"Enviar commits (git push) da pasta {_pretty(folder)}",
        f"Remoto: {shown}",
    ]
    if destination is not None:
        urls, elsewhere = destination
        lines.append(f"Endereço de envio do origin: {', '.join(urls)}")
        if elsewhere:
            lines.append(f"ATENÇÃO: {elsewhere} manda o git push para outro remoto")
    lines += warnings or []
    if state:
        branch, upstream, ahead = state
        lines.append(f"Branch atual: {branch}, upstream {upstream}")
        lines.append(f"Commits à frente do upstream: {ahead}")
    else:
        lines.append(
            f"Referências: {', '.join(names) if names else 'as configuradas no repositório'}"
        )
    given_url = remote is not None and PUSH_URL.match(remote) is not None
    if given_url:
        lines.append(f"ATENÇÃO: envia para um endereço escrito no comando: {cut(remote, 100)}")
    for override in overrides:
        lines.append(f"ATENÇÃO: {cut(override, 120)} muda o que o git roda ou para onde envia")
    if forced:
        lines.append(f"ATENÇÃO: {forced[0]} força o envio e pode reescrever o histórico do remoto")
    if deleted:
        lines.append("ATENÇÃO: apaga referências no remoto")
    extra = [name for name, _ in parsed.flags if name in ("--tags", "--all", "--mirror", "--prune")]
    if extra:
        lines.append("Opções: " + " ".join(extra))
    if moved:
        lines.append("Atenção: o comando muda de pasta; confira se é a pasta acima")
    flags = " ".join([*forced[:1], *(["--delete"] if deleted else []), *extra])
    refs = ", ".join(names) if names else "refs padrão"
    brief = f"{shown} ← git push {flags + ' ' if flags else ''}{refs} da pasta {_pretty(folder)}"
    alert = bool(given_url or overrides or forced or deleted or warnings)
    alert = alert or bool(destination and destination[1])
    return Finding(TITLE_GITHUB, tuple(lines), brief=brief, alert=alert)


def _is_plain_push(texts: list[str]) -> bool:
    """`git push` or `git push origin main`, with at most one `-q` or `--quiet`."""
    if texts[:2] != ["git", "push"]:
        return False
    rest = texts[2:]
    quiet = [word for word in rest if word in QUIET_FLAGS]
    if len(quiet) > 1:
        return False
    rest = [word for word in rest if word not in QUIET_FLAGS]
    return rest in ([], ["origin", "main"])


def _could_become_remote_key(word: Word) -> bool:
    """A config key with an expansion whose literal start leaves a push-destination key possible."""
    if not word.expands:
        return False
    start = re.split(r"[$`{]", word.text, maxsplit=1)[0].lower()
    return not start or any(
        key.startswith(start) or start.startswith(key) for key in REMOTE_KEY_STARTS
    )


def _git_config_in_environment(scan: Scan) -> list[str]:
    return [
        word.text
        for command in scan.commands
        for word in command.words
        if GIT_CONFIG_VARIABLE.match(word.text)
    ]


def _git(command: Command, args: list[Word], cwd: str, scan: Scan) -> list[Finding]:
    texts = [word.text for word in command.words]
    overrides = _risky_overrides(_git_overrides(args)) + _git_config_in_environment(scan)
    found = []
    _, verb_index = _split_git(args)
    pushing = verb_index is not None and args[verb_index].text == "push"
    if overrides and not pushing:
        found.append(
            Finding(
                TITLE_UNSURE,
                (
                    f"ATENÇÃO: {cut(overrides[0], 120)} muda o que o git roda ou para onde envia",
                    _line(texts),
                    "Confira o comando antes de aprovar.",
                ),
            )
        )
    return found + _git_verb(command, args, cwd, scan, overrides)


def _git_verb(
    command: Command, args: list[Word], cwd: str, scan: Scan, overrides: list[str]
) -> list[Finding]:
    texts = [word.text for word in command.words]
    directories, verb_index = _split_git(args)
    if verb_index is None:
        return []
    if args[verb_index].expands:
        return [_unsure(texts, "O subcomando do git vem de uma expansão (variável ou comando).")]
    verb, rest = args[verb_index].text, args[verb_index + 1 :]
    if verb.startswith("credential"):
        return [_git_credential(texts, verb)]
    if verb == "push":
        plain = _is_plain_push(texts) and not overrides and not _changes_directory(scan)
        destination = None
        warnings: list[str] = []
        if plain and _listed_for_push(cwd):
            bare = not any(word.text == "origin" for word in rest)
            destination = _push_destination(cwd, bare)
            allowed = _allowed_push_remotes()
            keys = _local_risky_keys(cwd)
            if keys is None:
                warnings = ["ATENÇÃO: não consegui ler a configuração local do repositório"]
            else:
                warnings = [
                    f"ATENÇÃO: a configuração local do repositório define {cut(key, 80)}"
                    for key in keys
                ]
            if (
                destination
                and not destination[1]
                and set(destination[0]) <= allowed
                and not warnings
            ):
                return []
        found = _push(rest, directories, cwd, _runs_cd(scan), overrides, destination, warnings)
        return [found]
    if verb == "remote":
        word = next((w for w in rest if not w.text.startswith("-")), None)
        if word is not None and word.expands:
            return [_unsure(texts, "A ação do git remote vem de uma expansão.")]
        if word is not None and word.text in REMOTE_CHANGES:
            return [
                Finding(
                    TITLE_REMOTE,
                    (f"Muda os remotos do repositório (git remote {word.text})", _line(texts)),
                )
            ]
    if verb == "config":
        parsed = parse_flags(rest, set())
        names = [word.text for word in parsed.positionals]
        reading = any(flag in CONFIG_READS for flag, _ in parsed.flags) or names[:1] in (
            ["get"],
            ["list"],
        )
        if reading:
            return []
        key = next((name for name in names if REMOTE_KEYS.match(name)), None)
        if key is None and parsed.positionals and _could_become_remote_key(parsed.positionals[0]):
            return [_unsure(texts, "A chave do git config vem de uma expansão.")]
        if key:
            return [
                Finding(
                    TITLE_REMOTE,
                    (f"Muda a configuração do git que decide o destino: {key}", _line(texts)),
                )
            ]
    return []


def _gh_repo(parsed: Parsed, cwd: str, given: str | None = None) -> str:
    repo = parsed.value("-R", "--repo") or given
    if repo:
        return repo
    return f"{_pretty(cwd)} (pasta atual)" if cwd else "o repositório atual"


def _gh_body(parsed: Parsed) -> str | None:
    body = parsed.value("-b", "--body")
    if body is not None:
        return body_summary(body)
    name = parsed.value("-F", "--body-file")
    return None if name is None else f"arquivo {name}"


def _query_is_expanded(args: list[Word]) -> bool:
    """Whether the shell fills in the GraphQL `query` field, so its text is not what runs."""
    for index, word in enumerate(args):
        if word.text in GH_API_FIELDS and index + 1 < len(args):
            value = args[index + 1]
            if value.expands and value.text.startswith("query="):
                return True
        elif word.expands and "query=" in word.text and word.text.startswith(("-f", "-F", "--f")):
            return True
    return False


def _gh_api(args: list[Word], cwd: str) -> Finding | None:
    parsed = parse_flags(args, GH_API_VALUES)
    names = [word.text for word in parsed.positionals]
    endpoint = names[0] if names else ""
    fields = [
        (flag, value) for flag, value in parsed.flags if flag in GH_API_FIELDS and value is not None
    ]
    method = parsed.value("-X", "--method")
    method = method.upper() if method else ("POST" if fields else "GET")
    if endpoint.strip("/") == "graphql":
        if not _query_is_expanded(args) and _graphql_is_read(fields, cwd):
            return None
        shown = "mutation ou consulta que não consegui ler"
        return Finding(TITLE_GITHUB, ("Consulta GraphQL (gh api graphql)", f"Conteúdo: {shown}"))
    if method in SAFE_METHODS:
        return None
    keys = ", ".join(value.partition("=")[0] for _, value in fields) or "sem campos"
    return Finding(
        TITLE_GITHUB,
        (f"Chamada à API do GitHub: {method} {endpoint or '(sem endereço)'}", f"Campos: {keys}"),
    )


def _graphql_is_read(fields: list[tuple[str, str]], cwd: str) -> bool:
    queries = [value.partition("=")[2] for _, value in fields if value.startswith("query=")]
    if len(queries) != 1 or any(flag == "--input" for flag, _ in fields):
        return False
    query = queries[0]
    if query.startswith("@"):
        try:
            query = Path(cwd, os.path.expanduser(query[1:])).read_text(encoding="utf-8")
        except (OSError, ValueError):
            return False
    return not re.search(r"\bmutation\b", query, re.IGNORECASE)


def _gh_change(
    group: str, action: str, tail: list[Word], cwd: str, texts: list[str], given: str | None
) -> Finding:
    """The box of a `gh` write; `given` is the `-R/--repo` typed before the action."""
    values = GH_MERGE_VALUES if (group, action) == ("pr", "merge") else GH_CHANGE_VALUES
    parsed = parse_flags(tail, values)
    target = parsed.positionals[0].text if parsed.positionals else None
    repo = _gh_repo(parsed, cwd, given)
    if (group, action) == ("pr", "create"):
        head = parsed.value("-H", "--head") or "a branch atual"
        base = parsed.value("-B", "--base") or "a branch padrão"
        lines = [f"Criar PR em {repo}: {head} → {base}"]
        if title := parsed.value("-t", "--title"):
            lines.append(f"Título: {title}")
        if body := _gh_body(parsed):
            lines.append(f"Corpo: {body}")
        if parsed.has("-d", "--draft"):
            lines.append("Como rascunho")
    elif (group, action) == ("pr", "merge"):
        method = next((GH_MERGE_METHODS[n] for n, _ in parsed.flags if n in GH_MERGE_METHODS), None)
        lines = [f"Mesclar o PR {target or 'da branch atual'} em {repo}"]
        lines.append(f"Método: {method or 'o padrão do repositório'}")
        if parsed.has("--admin"):
            lines.append("ATENÇÃO: --admin ignora as regras de proteção da branch")
        if parsed.has("-d", "--delete-branch"):
            lines.append("ATENÇÃO: --delete-branch apaga a branch depois de mesclar")
        if parsed.has("--auto"):
            lines.append("Mescla sozinho quando as checagens passarem (--auto)")
    elif group in ("pr", "issue") and action in ("comment", "edit", "close"):
        verb = {"comment": "Comentar", "edit": "Editar", "close": "Fechar"}[action]
        noun = "PR" if group == "pr" else "issue"
        lines = [f"{verb} {noun} {target or 'atual'} em {repo}"]
        if title := parsed.value("-t", "--title"):
            lines.append(f"Título: {title}")
        if body := _gh_body(parsed) or parsed.value("-c", "--comment"):
            lines.append(f"Texto: {body}")
    else:
        lines = [f"Comando do gh que altera algo fora: gh {cut(' '.join(texts), 100)}"]
    called = [flag for flag in GH_CALLED_OUT if parsed.has(flag)]
    if (group, action) == ("pr", "merge") and parsed.has("-d") and "--delete-branch" not in called:
        called.append("--delete-branch")
    for flag in called:
        if not any(line.startswith(f"ATENÇÃO: {flag}") for line in lines):
            lines.append(f"ATENÇÃO: {flag} no comando do gh")
    brief = f"{repo}: {lines[0].replace(f' em {repo}', '')}"
    if called:
        brief += f" ({' '.join(called)})"
    return Finding(TITLE_GITHUB, tuple(lines), brief=brief, alert=bool(called))


def _gh_flag_before_action(args: list[Word], positions: list[int]) -> bool:
    """Whether a flag other than `-R/--repo/--hostname` sits before the group or the action.

    gh's parser knows which flags take a value and the gate does not: in `gh pr --title view
    create`, `view` is the title and `create` runs.
    """
    end = positions[-1] if positions else len(args)
    index = 0
    while index < end:
        name, equals, _ = args[index].text.partition("=")
        index += 1
        if not name.startswith("-"):
            continue
        if name in GH_GLOBAL_VALUES:
            index += 0 if equals else 1
        elif name not in ("-h", "--help"):
            return True
    return False


def _gh(command: Command, args: list[Word], cwd: str) -> list[Finding]:
    texts = [word.text for word in command.words]
    top = parse_flags(args, GH_GLOBAL_VALUES)
    if not top.positionals:
        return []
    is_api = top.positionals[0].text == "api"
    if any(args[position].expands for position in top.positions[: 1 if is_api else 2]):
        return [_unsure(texts, "O subcomando do gh vem de uma expansão (variável ou comando).")]
    if _gh_flag_before_action(args, top.positions[: 1 if is_api else 2]):
        return [_unsure(texts, "Uma opção antes da ação do gh pode tomar a ação como valor.")]
    group = top.positionals[0].text
    action = top.positionals[1].text if len(top.positionals) > 1 else ""
    if group == "auth" and (
        action in ("token", "git-credential")
        or (action == "status" and top.has("-t", "--show-token"))
    ):
        return [
            Finding(
                TITLE_CREDENTIAL,
                (f"Lê uma credencial: o token do GitHub (gh auth {action})", _line(texts)),
            )
        ]
    if group in GH_ANY_ACTION or action in GH_READS.get(group, set()):
        return []
    if group == "api":
        api_args = args[top.positions[0] + 1 :]
        if any(
            word.bare and word.text[:1] and word.text[0] in INJECTING_START for word in api_args
        ):
            return [_unsure(texts, "Uma palavra do gh api vem de uma expansão e pode trazer -X.")]
        found = _gh_api(api_args, cwd)
        return [found] if found else []
    rest = args[top.positions[1] + 1 :] if action else []
    before = args[: top.positions[1]] if action else args
    given = parse_flags(before, GH_GLOBAL_VALUES).value("-R", "--repo")
    return [_gh_change(group, action, rest, cwd, [word.text for word in args], given)]


def _http(program: str, args: list[Word]) -> list[Finding]:
    curl = program == "curl"
    parsed = parse_flags(args, CURL_VALUE_FLAGS if curl else WGET_VALUE_FLAGS)
    flags = [name for name, _ in parsed.flags]
    if curl:
        data = any(f in CURL_DATA_SHORT or CURL_DATA.match(f) for f in flags)
        data = data and not parsed.has("-G", "--get")
        method = parsed.value("-X", "--request")
        if method is None and parsed.has("-I", "--head"):
            method = "HEAD"
    else:
        data = any(WGET_DATA.match(f) for f in flags)
        method = parsed.value("--method")
    method = method.upper() if method else ("POST" if data else "GET")
    if method in SAFE_METHODS and not data:
        return []
    urls = [word.text for word in parsed.positionals]
    url = next((u for u in urls if "://" in u), urls[0] if urls else "")
    try:
        parts = urlsplit(url if "://" in url else "//" + url)
        place = f"{parts.hostname or '?'}{':' + str(parts.port) if parts.port else ''}{parts.path}"
    except ValueError:
        place = cut(url, 60)
    lines = [f"{program} {method} → {place or 'destino não encontrado'}"]
    if data:
        lines.append("com dados")
    brief = f"{place or cut(url, 60)}: {program} {method}{' com dados' if data else ''}"
    return [Finding(TITLE_HTTP, tuple(lines), brief=brief)]


def _pending_summary(code: str) -> Finding:
    """The box for applying the pending preview `code`; a record that is not there is denied.

    Denied, not asked: a box that cannot show what `apply` will write is a rubber stamp.
    """
    path = _data_dir() / "cards" / "pending" / f"{code}.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Finding(
            TITLE_JIRA,
            (),
            f"Blocked: no pending preview with code {code} in the default store; "
            "run ws card preview first.",
        )
    except (OSError, ValueError):
        return Finding(
            TITLE_JIRA,
            (),
            f"Blocked: the pending preview with code {code} could not be read; "
            "run ws card preview again.",
        )
    summary = record.get("summary") if isinstance(record, dict) else None
    if not isinstance(summary, list) or not summary or not all(isinstance(s, str) for s in summary):
        line = f"A prévia {code} não tem resumo; confira com `ws card preview` antes de aprovar"
        return Finding(TITLE_JIRA, (line,))
    brief = f"Jira: aplicar a prévia {code} ({len(summary)} mudanças)"
    return Finding(TITLE_JIRA, (f"Aplicar a prévia {code}:", *summary), brief=brief)


def _store_change(scan: Scan) -> str | None:
    """A word of the command line that may point `ws` at a store other than the gate's."""
    for command in scan.commands:
        for word in command.words:
            if STORE_VARIABLE.match(word.text) or program_name(word.text) in STORE_PROGRAMS:
                return word.text
    return None


def _gate_catalog(texts: list[str], args: list[Word], top: Parsed) -> list[Finding]:
    """`ws gate catalog` lists; any action after it changes what the gate lets through."""
    rest = top.positionals[2:]
    if not rest:
        return []
    action, server, tools = rest[0].text, rest[1:2], rest[2:]
    if any(args[position].expands for position in top.positions[2:]):
        return [_unsure(texts, "A ação ou as ferramentas do catálogo vêm de uma expansão.")]
    effect = {"pass": "passam a ser liberadas sem caixa", "ask": "passam a pedir aprovação"}
    if action not in effect:
        line = f"Muda o catálogo do portão (ws gate catalog {action})"
    else:
        named = " ".join(word.text for word in server + tools) or "(nenhuma ferramenta)"
        line = f"Muda o catálogo do portão: {named} {effect[action]}"
    return [Finding(TITLE_PROTECTION, (cut(line, 150), _line(texts)))]


def _ws(command: Command, args: list[Word], scan: Scan) -> list[Finding]:
    texts = [word.text for word in command.words]
    top = parse_flags(args, set())
    names = [word.text for word in top.positionals[:2]]
    if any(args[position].expands for position in top.positions[:2]):
        return [_unsure(texts, "O subcomando do ws vem de uma expansão (variável ou comando).")]
    if names[:1] == ["mcp-headers"]:
        return [
            Finding(
                TITLE_CREDENTIAL,
                ("Lê uma credencial: os cabeçalhos dos MCPs (ws mcp-headers)", _line(texts)),
            )
        ]
    if names[:1] == ["setup"]:
        checking = any(len(flag) > 2 and "--check".startswith(flag) for flag, _ in top.flags)
        if checking:
            return []
        line = "Atualiza a cópia protegida dos hooks do Claude Code (ws setup)"
        return [Finding(TITLE_PROTECTION, (line, _line(texts)))]
    if names == ["gate", "catalog"]:
        return _gate_catalog(texts, args, top)
    if names != ["card", "apply"]:
        return []
    code = None
    for index, word in enumerate(args):
        flag, equals, value = word.text.partition("=")
        if len(flag) > 2 and "--approve".startswith(flag):
            code = value if equals else (args[index + 1].text if index + 1 < len(args) else "")
    if code is None:
        lines = ["ws card apply sem --approve; o ws vai recusar"]
    elif not APPROVE_CODE.fullmatch(code):
        lines = [f"Código de aprovação inválido ({cut(code, 30)}); o ws card apply vai recusar"]
    elif changed := _store_change(scan):
        reason = (
            f"ATENÇÃO: {cut(changed, 60)} pode mudar a pasta de onde o ws lê a prévia; "
            "a caixa não sabe o que será aplicado."
        )
        return [_unsure(texts, reason)]
    else:
        return [_pending_summary(code)]
    return [Finding(TITLE_JIRA, tuple(lines))]


def _python_ws(args: list[Word]) -> list[tuple[str, list[Word]]]:
    for index, word in enumerate(args):
        if word.text == "-m" and index + 1 < len(args):
            module, rest = args[index + 1].text, args[index + 2 :]
            if module in ("ws", "ws.cli", "ws.__main__"):
                return [("ws", rest)]
            if module.startswith("ws."):
                return [("ws", [Word(module.split(".")[1]), *rest])]
            return []
        if not word.text.startswith("-"):
            break
    return []


def _reads_unseen_commands(command: Command, name: str, args: list[Word]) -> str | None:
    """Why a shell or `eval` runs text the gate cannot read, or None."""
    if name == "eval":
        code = args
    elif name in shell.SHELLS:
        script = shell.script_word(args)
        if script is None and (command.piped or command.reads_file):
            if all(word.text.startswith("-") for word in args):
                return "O shell recebe os comandos por pipe ou arquivo; não dá para lê-los"
        code = [script] if script else []
    else:
        return None
    if code and code[0].expands and code[0].text.lstrip().startswith(("$", "`")):
        return "O script vem de uma expansão (variável ou comando); não dá para lê-lo"
    return None


def _invocation(
    command: Command, name: str, args: list[Word], cwd: str, scan: Scan
) -> list[Finding]:
    texts = [word.text for word in command.words]
    if reason := _reads_unseen_commands(command, name, args):
        return [_unsure(texts, reason)]
    if shell.PYTHON.fullmatch(name):
        return [
            finding
            for inner, inner_args in _python_ws(args)
            for finding in _invocation(command, inner, inner_args, cwd, scan)
        ]
    if name not in WATCHED:
        return []
    if name in ("curl", "wget", "ws") and any(word.bare for word in args):
        return [_unsure(texts, "Tem $, crase ou chaves fora de aspas; não sei o que vai rodar.")]
    if name == "git":
        return _git(command, args, cwd, scan)
    if name == "gh":
        return _gh(command, args, cwd)
    if name == "ws":
        return _ws(command, args, scan)
    return _http(name, args)


def _protection(command: Command) -> list[Finding]:
    texts = [word.text for word in command.words]
    index = shell.locate_program(texts)
    program = "" if index is None else program_name(texts[index])
    args = texts if index is None else texts[index + 1 :]
    if program in READ_ONLY | NAVIGATION:
        args = []
    elif program == "git" and next((t for t in args if not t.startswith("-")), "") in READ_ONLY_GIT:
        args = []
    hits = [path for path in command.writes if PROTECTED_PATH.search(path)]
    for text in args:
        if " " not in text and PROTECTED_PATH.search(text):
            hits.append(text)
        elif INTERPRETERS.fullmatch(program) and PROTECTED_IN_CODE.search(text):
            hits.append(text)
    if not hits:
        return []
    return [
        Finding(
            TITLE_PROTECTION,
            (f"Mexe na proteção do Claude Code: {_pretty(cut(hits[0], 100))}", _line(command)),
        )
    ]


def _harmless(command: Command) -> bool:
    texts = [word.text for word in command.words]
    index = shell.locate_program(texts)
    if command.writes:
        return False
    if index is None:
        return True
    program = program_name(texts[index])
    verb = next((t for t in texts[index + 1 :] if not t.startswith("-")), "")
    return program in HARMLESS or (program == "git" and verb in READ_ONLY_GIT)


def _after_entering_protection(scan: Scan) -> list[Finding]:
    entered = None
    for command in scan.commands:
        for name, args in shell.invocations(command)[:1]:
            if name in NAVIGATION and args and PROTECTED_DIRECTORY.search(args[-1].text):
                entered = args[-1].text
    if entered is None:
        return []
    for command in scan.commands:
        if not _harmless(command):
            return [
                Finding(
                    TITLE_PROTECTION,
                    (
                        f"Mexe na proteção do Claude Code: roda dentro de {_pretty(entered)}",
                        _line(command),
                    ),
                )
            ]
    return []


def _credential_places() -> set[str]:
    home = Path.home()
    return {
        os.path.normpath(_config_dir()),
        os.path.normpath(_config_dir() / "credentials"),
        os.path.normpath(home / ".config" / "workspace"),
        os.path.normpath(home / ".config" / "workspace" / "credentials"),
        os.path.normpath(home / ".config" / "gh"),
        os.path.normpath(home / ".config" / "gh" / "hosts.yml"),
        os.path.normpath(home / ".ssh"),
    }


def _credential_path(text: str, folder: str | None = None, recursive: bool = False) -> str | None:
    """The credential a path-like word names, or None.

    Covers the credentials file of `ws`, the `gh` hosts file, the `~/.ssh` private keys (`id_*`
    but not `.pub`), those folders themselves (a copy or an archive reads what is inside) and a
    glob that could match them. `folder` is the cwd or one the command entered with `cd`: a
    relative path is then looked up in it. `recursive`: the program reads whole trees (`grep -r`,
    `tar`, `cp -r`), so the home and `~/.config`, which hold the credentials, count too.
    """
    if folder is not None:
        if text.startswith(("/", "~", "$")):
            return None
        text = os.path.normpath(f"{folder.rstrip('/')}/{text}")
    if CREDENTIAL_FILE.search(text) or CREDENTIAL_FOLDER.search(text):
        return text
    if SSH_PRIVATE_KEY.search(text) and not text.endswith(".pub"):
        return text
    glob = CREDENTIAL_GLOB.search(text)
    if glob and any(
        fnmatch.fnmatchcase(name, glob.group(2)) for name in CREDENTIAL_SAMPLES[glob.group(1)]
    ):
        return text
    if _glob_names_credential(text, recursive):
        return text
    expanded = os.path.normpath(os.path.expandvars(os.path.expanduser(text)))
    if expanded in _credential_places():
        return text
    home = os.path.normpath(Path.home())
    if recursive and (PARENT_FOLDER.search(text) or expanded in (home, f"{home}/.config")):
        return text
    return None


def _glob_names_credential(text: str, recursive: bool) -> bool:
    """Whether a glob can match a credential, its folder or (`recursive`) a parent folder.

    Matched one path component at a time, as the shell does: `*` stops at `/` and does not match
    a leading dot. A pattern that does not start at the home is compared with the end of the path.
    """
    if not any(char in text for char in "*?["):
        return False
    pattern = text.rstrip("/")
    for prefix in ("$HOME", "${HOME}", str(Path.home())):
        if pattern == prefix or pattern.startswith(prefix + "/"):
            pattern = "~" + pattern[len(prefix) :]
    wanted = pattern.split("/")
    for target in CREDENTIAL_TARGETS + (PARENT_TARGETS if recursive else ()):
        parts = target.split("/")
        if pattern.startswith("~"):
            if len(parts) != len(wanted):
                continue
        elif len(wanted) > len(parts) - 1:
            continue
        else:
            parts = parts[len(parts) - len(wanted) :]
        if all(_component_matches(part, glob) for part, glob in zip(parts, wanted, strict=True)):
            return True
    return False


def _component_matches(name: str, glob: str) -> bool:
    if name.startswith(".") and not glob.startswith("."):
        return False
    return fnmatch.fnmatchcase(name, glob)


def _reads_trees(program: str, args: list[str]) -> bool:
    if program in RECURSIVE_PROGRAMS:
        return True
    if program == "find":
        return any(arg in FIND_RUNS for arg in args)
    letters, names = RECURSIVE_FLAGS.get(program, ("", ()))
    for arg in args:
        if arg in names:
            return True
        if arg.startswith("-") and not arg.startswith("--") and set(arg[1:]) & set(letters):
            return True
    return False


def _credential_in_code(code: str) -> str | None:
    for found in CREDENTIAL_IN_CODE.finditer(code):
        if not found.group().endswith(".pub"):
            return found.group()
    if CODE_HOME.search(code) and (name := CODE_CREDENTIAL_NAME.search(code)):
        return f"um caminho na home montado no código ({name.group()})"
    return None


def _entered_folders(scan: Scan) -> list[str]:
    folders = []
    for command in scan.commands:
        for name, args in shell.invocations(command)[:1]:
            if name in NAVIGATION and args:
                folders.append(args[-1].text)
    return folders


def _git_credential(texts: list[str], verb: str) -> Finding:
    return Finding(
        TITLE_CREDENTIAL,
        (f"Lê uma credencial: o ajudante de credenciais do git (git {verb})", _line(texts)),
    )


def _credentials(command: Command, folders: list[str]) -> list[Finding]:
    texts = [word.text for word in command.words]
    index = shell.locate_program(texts)
    program = "" if index is None else program_name(texts[index])
    args = texts if index is None else texts[index + 1 :]
    redirected = [*command.writes, *command.reads]
    hits = [path for text in redirected if (path := _credential_path(text))]
    metadata = program in METADATA_PROGRAMS or (
        program in TEST_PROGRAMS and bool(args) and args[0] in TEST_METADATA_FLAGS
    )
    recursive = _reads_trees(program, args)
    if not (metadata or program in NAVIGATION):
        for text in args:
            if " " in text:
                code = _credential_in_code(text) if INTERPRETERS.fullmatch(program) else None
                hits += [code] if code else []
                continue
            path = next(
                (p for f in (None, *folders) if (p := _credential_path(text, f, recursive))),
                None,
            )
            hits += [path] if path else []
    if not hits:
        return []
    return [
        Finding(
            TITLE_CREDENTIAL,
            (f"Lê uma credencial: {_pretty(cut(hits[0], 100))}", _line(command)),
        )
    ]


def _program_by_expansion(command: Command, whole: str) -> list[Finding]:
    """A program word built by an expansion: its name is unknown when it is in the last component.

    `$HOME/.local/bin/uv` names `uv`; `${c}l` may name `curl`, whatever the rest of the text cites.
    An expansion that ends after the last `/` leaves `}`, `)` or a backtick in the name.
    """
    texts = [word.text for word in command.words]
    index = shell.locate_program(texts)
    if index is None or not command.words[index].expands:
        return []
    if set(texts[index].rsplit("/", 1)[-1]) & set("$`{}()"):
        return [_unsure(texts, "O nome do programa vem de uma expansão; não sei o que vai rodar.")]
    if not NAMES.search(whole):
        return []
    return [_unsure(texts, "O nome do programa vem de uma expansão e o comando cita ws, gh, git…")]


def _names_watched_program(text: str) -> bool:
    name = program_name(text)
    return name in WATCHED and (text == name or text.endswith("/bin/" + name))


def _hidden_program(command: Command) -> list[Finding]:
    """A watched program named as an argument of a program that may run it (`xargs git push`).

    The gate reads a fixed list of wrappers; any other program that starts its arguments as a
    command (`xargs`, `find -exec`, `parallel`, an unknown wrapper) would hide the write.
    """
    texts = [word.text for word in command.words]
    index = shell.locate_program(texts)
    if index is None:
        return []
    program = program_name(texts[index])
    args = texts[index + 1 :]
    if (
        program in CATCH_ALL_HARMLESS
        or program in NAVIGATION
        or program in WATCHED
        or program in ("uv", "uvx")
        or (program == "sed" and "-n" in args and not any(a.startswith("-i") for a in args))
    ):
        return []
    for position, text in enumerate(texts[1:], start=1):
        if position == index or not _names_watched_program(text):
            continue
        if shell.PYTHON.fullmatch(program) and texts[position - 1] == "-m":
            continue
        return [
            _unsure(texts, f"O comando passa {text} como argumento de {program}; pode rodá-lo.")
        ]
    return []


def _wrapper_script_by_expansion(command: Command) -> list[Finding]:
    for script in shell.wrapper_scripts(command.words):
        if script.expands and script.text.lstrip().startswith(("$", "`")):
            texts = [word.text for word in command.words]
            return [_unsure(texts, "O script vem de uma expansão (variável ou comando).")]
    return []


def _script_findings(scan: Scan) -> list[Finding]:
    found = []
    for code in scan.scripts:
        if WS_BY_CODE.search(code):
            found.append(
                Finding(
                    TITLE_JIRA,
                    ("Código Python que chama o módulo ws: pode aplicar uma prévia de card",),
                )
            )
        if reading := _credential_in_code(code):
            found.append(
                Finding(
                    TITLE_CREDENTIAL,
                    (f"Lê uma credencial: {reading}", "Código Python que cita o arquivo"),
                )
            )
        if PROTECTED_IN_CODE.search(code):
            found.append(
                Finding(
                    TITLE_PROTECTION,
                    ("Mexe na proteção do Claude Code: código Python que cita settings ou hooks",),
                )
            )
    return found


def _combine(findings: list[Finding]) -> Decision:
    unique = list(dict.fromkeys(findings))
    if not unique:
        return PASS
    if denial := next((finding.denial for finding in unique if finding.denial), None):
        return deny(denial)
    if len(unique) == 1:
        return ask(unique[0].title, list(unique[0].lines))
    titles = {finding.title for finding in unique}
    title = titles.pop() if len(titles) == 1 else "Vários comandos pedem aprovação"
    return ask(title, [finding.compact() for finding in unique])


def decide(command: str, cwd: str) -> Decision:
    scan = shell.scan(command)
    findings: list[Finding] = []
    folders = ([cwd] if cwd else []) + _entered_folders(scan)
    for each in scan.commands:
        findings += _protection(each)
        findings += _credentials(each, folders)
        findings += _program_by_expansion(each, command)
        findings += _hidden_program(each)
        findings += _wrapper_script_by_expansion(each)
        for name, args in shell.invocations(each):
            findings += _invocation(each, name, args, cwd, scan)
    findings += _after_entering_protection(scan)
    findings += _script_findings(scan)
    if scan.overrun:
        findings.append(
            Finding(
                TITLE_UNSURE,
                (
                    "O comando é grande ou aninhado demais para ler a tempo",
                    "Confira o comando antes de aprovar.",
                ),
            )
        )
    elif scan.unparsed and NAMES.search(command):
        findings.append(
            Finding(
                TITLE_UNSURE,
                (
                    "O comando tem aspas ou parênteses que não consegui ler e cita ws, gh, git, "
                    "curl ou wget",
                    "Confira o comando antes de aprovar.",
                ),
            )
        )
    return _combine(findings)
