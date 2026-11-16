"""The approval gate's rules for Bash: which commands write outside the machine, and the box text.

`decide(command, cwd)` splits the command with `shell.scan` (so `bash -c`, `eval`, `$(...)` and
heredocs are looked at) and returns one decision. A variable the command assigns a literal value
(`A="git -C x"; $A log`) is resolved first by `variables.worlds`, and every resolved text is
judged; the strictest decision wins. Families, each with its own PT-BR box: `git push` (and what
redirects it), `gh`, `curl`/`wget`, `ws card apply`, `ws release publish|move`, `ws observe run`
(it queries the production replica; the box lists the plan's database checks, never their SQL),
the protection of the Claude Code settings and hooks, and commands the gate cannot read with
certainty. Everything else passes.

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

Text rules cannot see a script file the command runs, text piped to `node`, programs that start
other programs (`xargs`, `find -exec`, `ssh`) or a `cwd` that Claude Code reports stale.
Python is read from its own argv (`shell.parse_python`), runner modules (`-m cProfile -m ws`)
included: the code in `-c`, heredocs, static here-strings and `timeit`/`pdb -c` arguments is
scanned; code that comes from a pipe, a file or an expansion asks, also behind `-i`, a REPL module
or `code.interact()`; the program's own arguments that read a `ws` write are judged as `ws`; and a
`subprocess`/`os.system`/`os.exec*` call with a literal command that names `ws` is judged as
that command line.
Credential reads from code are found by the path written in it, or by the home plus a credential
name (`Path.home() / ... "credentials"`); a path built from pieces that name neither
(`"~/.c" + "laude/.cred" + "entials.json"`) is an accepted limit.
The push box runs three local, read-only `git` queries to name the branch (see `_branch_state`).
With `environment_branches` set, a push to one of them is denied, or asks with a warning in a
`direct_push_repos` repository (`branches`); the repository name comes from one more local query.

A plain `git push` (or `git push origin main`) shows no box only when all of these hold, in
`[gate]` of `~/.config/workspace/config.toml`: it is the whole command line (no other command,
assignment or redirection); the cwd is listed in `push_without_asking`; every
push URL of `origin` (`git remote get-url --push --all origin`) is listed in `push_remotes`; a
bare `git push` is not sent to another remote by `branch.*.pushRemote`, `remote.pushDefault` or
`branch.*.remote`; and the repository's local or worktree config (included files too) sets none
of the keys that run a program or redirect the push (`LOCAL_RISKY_KEYS`; `core.hooksPath` only
when it resolves to the repository's own `.githooks`). `.git/config` can
change outside the gate (the Edit tool is not in its matcher), so these are read from git at each
push, with the repository's `fsmonitor` and hooks off. A missing list, a mismatch or a failed
query asks, and the box shows the real push URL and the names (never the values) of the keys.
"""

import ast
import fnmatch
import json
import os
import posixpath
import re
import shlex
import subprocess
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import branches, shell, variables
from .decision import PASS, Decision, ask, body_summary, cut, deny, trigger
from .shell import Command, Scan, Word, program_name

TITLE_GITHUB = "Grava no GitHub"
TITLE_PUSH = "Envia commits para o GitHub"
TITLE_JIRA = "Grava no Jira"
TITLE_HTTP = "Envia dados para fora"
TITLE_PROTECTION = "Mexe na proteção do Claude Code"
TITLE_UNSURE = "Não sei o que este comando faz"
TITLE_UNSURE_PROGRAM = "Não sei qual programa este comando roda"
TITLE_REMOTE = "Muda o destino do git push"
TITLE_CREDENTIAL = "Lê uma credencial"
TITLE_REPLICA = "Consulta a réplica de produção"

WATCHED = {"git", "gh", "curl", "wget", "ws"}
NAMES = re.compile(r"\b(?:ws|gh|git|curl|wget)\b")
APPROVE_CODE = re.compile(r"[0-9a-f]{12}")
WS_WORD = re.compile(r"\bws\b")
WS_IMPORT = re.compile(r"\b(?:from|import)\s+ws\b|(?:import_module|__import__)\(\s*['\"]ws\b")
WS_MODULES = {"ws", "ws.cli", "ws.__main__"}
WS_WRITES = {("card", "apply"), ("release", "publish"), ("release", "move"), ("observe", "run")}
WRITE_WORDS = re.compile(r"\b(?:card\s+apply|release\s+(?:publish|move)|observe\s+run)\b")
OBSERVE_VALUE_FLAGS = ("--day", "--check", "--project")
TASK_REF = re.compile(r"[A-Z][A-Z0-9_]*-[1-9]\d*")
PROJECT_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
DEFAULT_DATABASE = "replica"
MAX_PLAN_BYTES = 1 << 20
PLAN_FOLDER = re.compile(r"\bobservations\b")
SED_IN_PLACE = re.compile(r"-[^-]*i|--in-place")
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
CODE_WRITES = re.compile(
    r"\bopen\([^\n]*?,\s*(?:mode\s*=\s*)?['\"][rbt]*[wax+]"
    r"|\.open\(\s*(?:mode\s*=\s*)?['\"][rbt]*[wax+]"
    r"|write_text|write_bytes|\bshutil\b|\bunlink\b|\bchmod\b|\bchown\b|\.rename\("
    r"|\.symlink_to\(|\.touch\(|\bsubprocess\b|O_(?:WRONLY|RDWR|CREAT|APPEND|TRUNC)\b"
    r"|\bos\.(?:replace|rename|remove|rmdir|symlink|link|truncate|system|popen|exec|spawn)"
)
PROTECTED_DIRECTORY = re.compile(r"(?:^|/)(?:\.claude(?:/hooks)?|\.githooks)/?$")

CREDENTIAL_FILE = re.compile(
    r"(?:^|/)(?:\.config/(?:workspace/credentials|gh/hosts\.yml)|\.claude/\.credentials\.json"
    r"|\.git-credentials)$"
)
CREDENTIAL_FOLDER = re.compile(r"(?:^|/)(?:\.config/workspace|\.config/gh|\.ssh)/?$")
CREDENTIAL_GLOB = re.compile(r"(?:^|/)(\.config/workspace|\.config/gh|\.ssh)/([^/]*[*?\[][^/]*)$")
SSH_PRIVATE_KEY = re.compile(r"(?:^|/)\.ssh/id_[^/]*$")
CREDENTIAL_IN_CODE = re.compile(
    r"\.config/workspace/credentials|\.config/gh/hosts\.yml|\.ssh/id_[\w.-]*"
    r"|\.claude/\.credentials\.json|\.git-credentials"
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
    "~/.claude/.credentials.json",
    "~/.git-credentials",
    "~/.config/workspace",
    "~/.config/gh",
    "~/.ssh",
)
PARENT_TARGETS = ("~", "~/.config", "~/.claude")
MAX_BRACE_WORDS = 64
PARENT_FOLDER = re.compile(
    r"(?:^|/)\.config/?$|^(?:~|\$HOME|\$\{HOME\})(?:/\.claude)?/?$|^/(?:home/?)?$"
)
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
BENIGN_PROGRAM_KEYS = re.compile(
    r"^(?:core\.(?:pager|editor)|sequence\.editor|pager\..+|diff\.external)$"
)
BENIGN_PROGRAM_VALUES = {"", "cat", "less", "true", ":"}
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
MAX_WORD = 4096
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
API_REPO_PATH = re.compile(r"^repos/([^/]+)/([^/]+)/(.+)$")
API_PULL_MERGE = re.compile(r"pulls/(\d+)/merge")
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
    reason: str = ""
    snippet: str = ""

    def compact(self, times: int = 1) -> list[str]:
        """Its lines in a box shared with other findings: the reason, then what triggered it.

        A finding without a reason gives its summary and keeps its own warnings."""
        if self.reason:
            count = f" ({times} vezes)" if times > 1 else ""
            text = f"{self.reason}{count} — {trigger(self.snippet)}"
            return [f"ATENÇÃO: {text}" if self.alert else text]
        warnings = [line for line in self.lines if line.startswith("ATENÇÃO:")]
        return [self.brief or self.title, *warnings]

    def key(self) -> tuple[str, str, bool]:
        return (self.title, self.reason or self.brief or "\n".join(self.lines), self.alert)


def _found(title: str, reason: str, snippet: str, alert: bool = False) -> Finding:
    """A finding that is one line: why, and the piece of the command that triggered it."""
    found = Finding(title, (), alert=alert, reason=reason, snippet=snippet)
    return Finding(title, tuple(found.compact()), alert=alert, reason=reason, snippet=snippet)


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


def _snippet(command: Command | list[str]) -> str:
    """The command as one text; `trigger` cuts it to the piece the user looks for."""
    texts = command if isinstance(command, list) else [word.text for word in command.words]
    return " ".join(texts)


def _unsure(texts: list[str], reason: str, title: str = TITLE_UNSURE) -> Finding:
    """Not a danger, just not understood: the trigger starts at the first word the shell expands."""
    start = next((i for i, text in enumerate(texts) if "$" in text or "`" in text), 0)
    return _found(title, reason, _snippet(texts[start:]))


def _short_url(url: str) -> str:
    """A remote URL without scheme, user and password, and without the `.git` at the end."""
    text = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", url)
    return re.sub(r"^[^/@]*@", "", text).removesuffix(".git")


OWN_REPO_ENVIRONMENT = (
    "ATENÇÃO: branch de ambiente num repo de push_without_asking; "
    "o push não está sozinho no comando"
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


def _benign_override(override: str) -> bool:
    """A `-c` pager, editor or external diff set to a program that runs nothing else."""
    if not override.startswith("-c "):
        return False
    key, equals, value = override[3:].partition("=")
    key = key.lower()
    benign = bool(equals) and value in BENIGN_PROGRAM_VALUES
    return benign and BENIGN_PROGRAM_KEYS.match(key) is not None


def _risky_overrides(overrides: list[str]) -> list[str]:
    return [
        override
        for override in overrides
        if RISKY_GIT_KEYS.match(_override_key(override)) and not _benign_override(override)
    ]


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
    """Keys of the repository's own config that run a program or redirect a push; None if git
    cannot tell. Only the names leave this function: a value may hold a secret.

    Every scope is read (`--show-scope`), so the worktree config and included files count, but
    only `local` and `worktree` keys are kept: the global config is the user's own.
    """
    deadline = time.monotonic() + BRANCH_QUERY_TIMEOUT
    query = ["config", "--show-scope", "--get-regexp", LOCAL_RISKY_KEYS]
    done = _local_git(folder, query, deadline)
    if done is None or done.returncode not in (0, 1):
        return None
    keys = []
    for line in done.stdout.splitlines():
        scope, _, setting = line.partition("\t")
        key, _, value = setting.partition(" ")
        if scope not in ("local", "worktree"):
            continue
        if key == "core.hookspath" and _own_hooks(folder, value.strip(), deadline):
            continue
        if key and key not in keys:
            keys.append(key)
    return keys


def _own_hooks(folder: str, value: str, deadline: float) -> bool:
    """Whether a `core.hooksPath` value is the repository's own `.githooks` folder.

    `ws setup` writes `.githooks`; git takes a relative value from the top of the work tree.
    """
    if not value:
        return False
    done = _local_git(folder, ["rev-parse", "--show-toplevel"], deadline)
    top = done.stdout.strip() if done is not None and done.returncode == 0 else ""
    if not top or "\n" in top:
        return False
    hooks = os.path.join(top, os.path.expanduser(value))
    return os.path.realpath(hooks) == os.path.realpath(os.path.join(top, ".githooks"))


def _allowed_push_remotes() -> set[str]:
    try:
        with open(_config_dir() / "config.toml", "rb") as handle:
            listed = tomllib.load(handle)["gate"]["push_remotes"]
        return {url for url in listed if isinstance(url, str)}
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def _branch_state(folder: str, deadline: float) -> tuple[str, str, int] | None:
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


def _refspec_target(spec: str) -> str | None:
    """The remote branch a refspec writes: `HEAD` for the current branch's name, "" for a ref
    that is not a branch (a tag), None when the gate cannot tell."""
    spec = spec.removeprefix("+")
    colon = ":" in spec
    target = spec.rpartition(":")[2]
    if target in ("HEAD", "@"):
        return None if colon else "HEAD"
    if target.startswith("refs/heads/"):
        target = target.removeprefix("refs/heads/")
    elif target.startswith("refs/"):
        return ""
    return target or None


def _current_branch(folder: str, deadline: float) -> str | None:
    done = _local_git(folder, ["rev-parse", "--abbrev-ref", "HEAD"], deadline)
    answer = done.stdout.strip() if done is not None and done.returncode == 0 else ""
    return answer if answer and answer != "HEAD" and "\n" not in answer else None


def _push_repo(remote: Word | None, folder: str | None, deadline: float) -> str | None:
    """The name of the repository a push writes to: from the URL written in the command, or from
    the push URL of the remote (`origin` when none is named); None when the gate cannot tell."""
    if remote is not None and remote.expands:
        return None
    if remote is not None and PUSH_URL.match(remote.text):
        return branches.repo_name(remote.text)
    if folder is None or not _in_repository(folder):
        return None
    name = remote.text if remote is not None else "origin"
    done = _local_git(folder, ["remote", "get-url", "--push", name], deadline)
    url = done.stdout.strip() if done is not None and done.returncode == 0 else ""
    return branches.repo_name(url) if url and "\n" not in url else None


def _push_environment(
    rules: branches.Policy,
    parsed: Parsed,
    specs: list[Word],
    remote: Word | None,
    folder: str | None,
    state: tuple[str, str, int] | None,
    deadline: float,
) -> tuple[list[str], str]:
    """The environment-branch policy of one push: (box warnings, denial).

    `folder` is None when the push may run in another repository, so nothing is read there.
    Without a refspec the push goes to the upstream branch (`push.default` simple or upstream).
    """
    flag = next((name for name, _ in parsed.flags if name in ("--all", "--mirror")), "")
    targets: list[str | None] = []
    if specs:
        for word in specs:
            target = None if word.expands else _refspec_target(word.text)
            if target == "HEAD":
                target = _current_branch(folder, deadline) if folder else None
            targets.append(target)
    elif not (flag or parsed.has("--tags", "--delete", "-d")):
        targets.append(state[1].partition("/")[2] if state else None)
    environment = [target for target in targets if target and rules.is_environment(target)]
    unknown = [branches.UNKNOWN_TARGET] if None in targets else []
    if not (flag or environment):
        return unknown, ""
    if remote is None and state is not None:
        remote = Word(state[1].partition("/")[0])
    repo = _push_repo(remote, folder, deadline)
    warning, denied = branches.judge(rules, environment[0] if environment else "*", repo, flag)
    return [warning, *unknown], denied


def _push(
    rest: list[Word],
    directories: list[Word],
    cwd: str,
    moved: bool,
    overrides: list[str],
    destination: tuple[list[str], str | None] | None = None,
    warnings: list[str] | None = None,
    elsewhere: list[str] | None = None,
) -> Finding:
    parsed = parse_flags(rest, PUSH_VALUE_FLAGS)
    specs = list(parsed.positionals)
    given = parsed.value("--repo")
    remote_word = Word(given) if given is not None else None
    if remote_word is None and specs:
        remote_word, specs = specs[0], specs[1:]
    remote = remote_word.text if remote_word is not None else None
    names = [word.text for word in specs]
    forced = [name for name, _ in parsed.flags if name.startswith(FORCE_FLAGS)]
    forced += ["+" + spec[1:] for spec in names if spec.startswith("+")]
    deleted = parsed.has("--delete", "-d") or any(spec.startswith(":") for spec in names)
    folder = _folder(cwd, directories)
    redirecting = [override for override in overrides if _redirects_push(override)]
    readable = not (moved or elsewhere or any(word.expands for word in directories))
    deadline = time.monotonic() + BRANCH_QUERY_TIMEOUT
    state = None
    if readable and not names:
        state = _branch_state(folder, deadline)
    environment: list[str] = []
    denied = ""
    if rules := branches.policy():
        environment, denied = _push_environment(
            rules, parsed, specs, remote_word, folder if readable else None, state, deadline
        )
    if denied and readable and _listed_for_push(folder):
        # The user's own repo (push_without_asking) pushes to its main without asking when the
        # push is alone on the line; in a longer line it asks instead of being denied.
        environment, denied = [OWN_REPO_ENVIRONMENT], ""
    if denied:
        return Finding(TITLE_PUSH, (), denial=denied)
    if redirecting:
        shown = f"{remote or 'o remoto padrão'} (mudado por {cut(redirecting[0], 40)})"
    elif remote is not None and PUSH_URL.match(remote):
        shown = _short_url(remote)
    else:
        shown = remote or "o remoto padrão"
    if destination is not None and destination[0]:
        shown += f" ({', '.join(_short_url(url) for url in destination[0])})"
    left = state[0] if state else (", ".join(names) or "as refs configuradas")
    summary = f"{left} → {shown}"
    if state:
        ahead = state[2]
        summary += f", {ahead} commit{'' if str(ahead) == '1' else 's'} à frente"
    extra = [name for name, _ in parsed.flags if name in ("--tags", "--all", "--mirror", "--prune")]
    if extra:
        summary += f" ({' '.join(extra)})"
    if directories or moved:
        summary += f", pasta {_pretty(folder)}" + (" (o comando muda de pasta)" if moved else "")
    lines = [summary, *environment]
    if destination is not None and destination[1]:
        lines.append(f"ATENÇÃO: {destination[1]} manda o git push para outro remoto")
    lines += warnings or []
    lines += [
        f"ATENÇÃO: {cut(where, 100)} faz o git push usar outro repositório; a branch não foi lida"
        for where in elsewhere or []
    ]
    given_url = remote is not None and PUSH_URL.match(remote) is not None
    if given_url:
        lines.append(f"ATENÇÃO: envia para um endereço escrito no comando: {cut(remote, 100)}")
    for override in overrides:
        lines.append(f"ATENÇÃO: {cut(override, 120)} muda o que o git roda ou para onde envia")
    if forced:
        lines.append(f"ATENÇÃO: {forced[0]} força o envio e pode reescrever o histórico do remoto")
    if deleted:
        lines.append("ATENÇÃO: apaga referências no remoto")
    alert = bool(
        given_url or overrides or forced or deleted or warnings or elsewhere or environment
    )
    alert = alert or bool(destination and destination[1])
    brief = summary
    return Finding(TITLE_PUSH, tuple(lines), brief=brief, alert=alert)


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


def _other_repository(command: Command, args: list[Word], scan: Scan) -> list[str]:
    """What makes a push use a repository other than the one in its folder, as typed.

    `--git-dir`, `--work-tree`, a `GIT_DIR`-like variable, `env -C` and a `-C` from an expansion:
    the branch query would describe the cwd's repository, so the box must not show it.
    """
    found = []
    index = 0
    while index < len(args) and args[index].text.startswith("-"):
        option = args[index].text
        index += 1
        if option.startswith(("--git-dir=", "--work-tree=")):
            found.append(option)
        elif option in ("--git-dir", "--work-tree", "-C") and index < len(args):
            if option != "-C" or args[index].expands:
                found.append(f"{option} {args[index].text}")
            index += 1
        elif option in GIT_VALUE_OPTIONS:
            index += 1
    texts = [word.text for word in command.words]
    program = shell.locate_program(texts)
    wrapper = ""
    for position, text in enumerate(texts[:program]):
        if program_name(text) in shell.WRAPPERS:
            wrapper = program_name(text)
        elif text.startswith("--chdir="):
            found.append(f"{wrapper} {text}".strip())
        elif text in ("-C", "--chdir", "-D") and position + 1 < len(texts):
            found.append(f"{wrapper} {text} {texts[position + 1]}".strip())
    found += [
        word.text
        for each in scan.commands
        for word in each.words
        if GIT_DIRECTORY_VARIABLE.match(word.text)
    ]
    return list(dict.fromkeys(found))


def _only_command(scan: Scan, command: Command) -> bool:
    """Whether `command` is the whole command line: nothing before or after it, no redirection."""
    return (
        len(scan.commands) == 1
        and scan.commands[0] is command
        and not (scan.unparsed or scan.scripts or scan.overrun)
        and not (command.writes or command.reads or command.inner or command.piped)
        and command.here_string is None
    )


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
    overrides = _risky_overrides(_git_overrides(args)) + _git_config_in_environment(scan)
    found = []
    _, verb_index = _split_git(args)
    pushing = verb_index is not None and args[verb_index].text == "push"
    if overrides and not pushing:
        found.append(
            _found(
                TITLE_REMOTE,
                "Config na linha muda o que o git roda ou o destino",
                overrides[0],
                alert=True,
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
        return [_unsure(texts, "O subcomando do git vem de uma variável ou comando")]
    verb, rest = args[verb_index].text, args[verb_index + 1 :]
    if verb.startswith("credential"):
        return [_git_credential(texts, verb)]
    if verb == "push":
        plain = _is_plain_push(texts) and not overrides and not _changes_directory(scan)
        plain = plain and _only_command(scan, command)
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
        elsewhere = _other_repository(command, args, scan)
        moved = _runs_cd(scan)
        found = _push(rest, directories, cwd, moved, overrides, destination, warnings, elsewhere)
        return [found]
    if verb == "remote":
        word = next((w for w in rest if not w.text.startswith("-")), None)
        if word is not None and word.expands:
            return [_unsure(texts, "A ação do git remote vem de uma variável")]
        if word is not None and word.text in REMOTE_CHANGES:
            return [
                _found(TITLE_REMOTE, f"Muda os remotos (git remote {word.text})", _snippet(texts))
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
            return [_unsure(texts, "A chave do git config vem de uma variável")]
        if key:
            return [_found(TITLE_REMOTE, "Muda a config que decide o destino", key, alert=True)]
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


def _gh_api(args: list[Word]) -> Finding | None:
    parsed = parse_flags(args, GH_API_VALUES)
    names = [word.text for word in parsed.positionals]
    endpoint = names[0] if names else ""
    fields = [
        (flag, value) for flag, value in parsed.flags if flag in GH_API_FIELDS and value is not None
    ]
    method = parsed.value("-X", "--method")
    method = method.upper() if method else ("POST" if fields else "GET")
    if endpoint.strip("/") == "graphql":
        if _graphql_from_file(fields):
            shown = "A consulta vem de arquivo ou da entrada"
        elif not _query_is_expanded(args) and _graphql_is_read(fields):
            return None
        else:
            shown = "Mutation (grava) ou consulta que não consegui ler"
        return _found(TITLE_GITHUB, shown, "gh api graphql")
    if method in SAFE_METHODS:
        return None
    keys = ", ".join(value.partition("=")[0] for _, value in fields) or "sem campos"
    title = f"Grava na API do GitHub: {method} {endpoint or '(sem endereço)'}"
    return Finding(title, (f"Campos: {keys}",), brief=title)


def _graphql_from_file(fields: list[tuple[str, str]]) -> bool:
    """Whether the query comes from a file or stdin (`query=@f`, `--input`).

    The hook never reads it: the file can change before `gh` runs, or never end (`/dev/zero`).
    """
    return any(flag == "--input" or value.startswith("query=@") for flag, value in fields)


def _graphql_is_read(fields: list[tuple[str, str]]) -> bool:
    queries = [value.partition("=")[2] for _, value in fields if value.startswith("query=")]
    if len(queries) != 1:
        return False
    return not re.search(r"\bmutation\b", queries[0], re.IGNORECASE)


def _api_fields(args: list[Word]) -> list[tuple[str, str, bool]]:
    """The `gh api` fields as (flag, value, expands); `--input` gives its file name."""
    found = []
    for index, word in enumerate(args):
        text = word.text
        if text in GH_API_FIELDS and index + 1 < len(args):
            value = args[index + 1]
            found.append((text, value.text, value.expands))
        elif text.startswith(("--field=", "--raw-field=", "--input=")):
            flag, _, value = text.partition("=")
            found.append((flag, value, word.expands))
        elif text[:2] in ("-f", "-F") and len(text) > 2:
            found.append((text[:2], text[2:], word.expands))
    return found


def _api_branch(fields: list[tuple[str, str, bool]], key: str) -> tuple[bool, str | None]:
    """(present, value) of one field; the value is None when the shell or a file fills it in,
    and an `--input` body may hold any field."""
    present, value = False, None
    for flag, text, expands in fields:
        if flag == "--input":
            present, value = True, None
            continue
        name, equals, given = text.partition("=")
        if equals and name == key:
            unreadable = expands or (flag in ("-F", "--field") and given.startswith("@"))
            present, value = True, None if unreadable else given
    return present, value


def _gh_api_environment(
    rules: branches.Policy, args: list[Word], cwd: str
) -> tuple[list[str], str]:
    """The environment-branch policy of a `gh api` write: (box warnings, denial).

    Covers file writes (`contents/...`, branch from the `branch` field, the default branch when
    it is missing), ref updates (`git/refs/heads/<branch>`, or `git/refs` with a `ref` field) and
    server-side merges (`merges`, branch from `base`). A PR merge (`pulls/N/merge`) is judged by
    its base, as `gh pr merge` is.
    """
    parsed = parse_flags(args, GH_API_VALUES)
    if not parsed.positionals:
        return [], ""
    endpoint = parsed.positionals[0]
    found = API_REPO_PATH.match(endpoint.text.split("?", 1)[0].strip("/"))
    if found is None:
        return [], ""
    owner, name, rest = found.groups()
    merge = API_PULL_MERGE.fullmatch(rest)
    if merge is not None:
        base = None
        if not endpoint.expands:
            repo = None if "{" in owner + name else f"{owner}/{name}"
            base = branches.BaseLookup(merge.group(1), repo, cwd).result()
        line, denied = branches.judge_merge(rules, base, merge.group(1))
        return ([line] if line else []), denied
    fields = _api_fields(args)
    default = False
    branch: str | None = None
    if rest == "contents" or rest.startswith("contents/"):
        present, branch = _api_branch(fields, "branch")
        default = not present
    elif rest.startswith("git/refs/heads/"):
        if not endpoint.expands:
            branch = unquote(rest.removeprefix("git/refs/heads/"))
    elif rest in ("git/refs", "merges"):
        _, branch = _api_branch(fields, "ref" if rest == "git/refs" else "base")
        if branch is not None and rest == "git/refs":
            if not branch.startswith("refs/heads/"):
                return [], ""
            branch = branch.removeprefix("refs/heads/")
    else:
        return [], ""
    if endpoint.expands:
        repo = None
    elif name == "{repo}":
        repo = _push_repo(None, cwd or None, time.monotonic() + BRANCH_QUERY_TIMEOUT)
    else:
        repo = name
    if branch is None and not default:
        return [branches.UNKNOWN_TARGET], ""
    warning, denied = branches.judge(rules, branch, repo)
    return ([warning] if warning else []), denied


def _merge_base(
    rules: branches.Policy, parsed: Parsed, given: str | None, cwd: str
) -> tuple[str, str]:
    """The base of the PR a `gh pr merge` names, judged by the policy: (box line, denial)."""
    word = parsed.positionals[0] if parsed.positionals else None
    repo = parsed.value("-R", "--repo") or given
    if (word is not None and word.expands) or (repo and repo[:1] in INJECTING_START):
        return branches.UNKNOWN_BASE, ""
    ref = word.text if word is not None else None
    base = branches.BaseLookup(ref, repo, cwd).result()
    return branches.judge_merge(rules, base, ref)


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
        title = f"Cria PR em {repo}"
        lines = [f"{head} → {base}" + (" (rascunho)" if parsed.has("-d", "--draft") else "")]
        if text := parsed.value("-t", "--title"):
            lines.append(f"Título: {text}")
    elif (group, action) == ("pr", "merge"):
        method = next((GH_MERGE_METHODS[n] for n, _ in parsed.flags if n in GH_MERGE_METHODS), None)
        title = f"Mescla a PR {target or 'da branch atual'} em {repo}"
        lines = []
        if rules := branches.policy():
            line, denied = _merge_base(rules, parsed, given, cwd)
            if denied:
                return Finding(TITLE_GITHUB, (), denial=denied)
            lines.append(line)
        lines.append(f"Método: {method or 'o padrão do repositório'}")
        if parsed.has("--admin"):
            lines.append("ATENÇÃO: --admin ignora as regras de proteção da branch")
        if parsed.has("-d", "--delete-branch"):
            lines.append("ATENÇÃO: --delete-branch apaga a branch depois de mesclar")
        if parsed.has("--auto"):
            lines.append("Mescla sozinho ao passar as checagens (--auto)")
    elif group in ("pr", "issue") and action in ("comment", "edit", "close"):
        verb = {"comment": "Comenta", "edit": "Edita", "close": "Fecha"}[action]
        noun = "a PR" if group == "pr" else "a issue"
        title = f"{verb} {noun} {target or 'atual'} em {repo}"
        lines = []
        if text := parsed.value("-t", "--title"):
            lines.append(f"Título: {text}")
        if body := _gh_body(parsed) or parsed.value("-c", "--comment"):
            lines.append(f"Texto: {body}")
    else:
        title = "Altera algo fora, pelo gh"
        lines = [f"Comando do gh — {trigger('gh ' + ' '.join(texts))}"]
    called = [flag for flag in GH_CALLED_OUT if parsed.has(flag)]
    if (group, action) == ("pr", "merge") and parsed.has("-d") and "--delete-branch" not in called:
        called.append("--delete-branch")
    for flag in called:
        if not any(line.startswith(f"ATENÇÃO: {flag}") for line in lines):
            lines.append(f"ATENÇÃO: {flag} no comando do gh")
    brief = title + (f" ({' '.join(called)})" if called else "")
    return Finding(title, tuple(lines), brief=brief, alert=bool(called))


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
        return [_unsure(texts, "O subcomando do gh vem de uma variável ou comando")]
    if _gh_flag_before_action(args, top.positions[: 1 if is_api else 2]):
        return [_unsure(texts, "Uma opção antes da ação do gh pode virar o valor dela")]
    group = top.positionals[0].text
    action = top.positionals[1].text if len(top.positionals) > 1 else ""
    if group == "auth" and (
        action in ("token", "git-credential")
        or (action == "status" and top.has("-t", "--show-token"))
    ):
        return [
            _found(
                TITLE_CREDENTIAL,
                f"Lê o token do GitHub (gh auth {action})",
                _snippet(texts),
                alert=True,
            )
        ]
    if group in GH_ANY_ACTION or action in GH_READS.get(group, set()):
        return []
    if group == "api":
        api_args = args[top.positions[0] + 1 :]
        if any(
            word.bare and word.text[:1] and word.text[0] in INJECTING_START for word in api_args
        ):
            return [_unsure(texts, "Uma palavra do gh api vem de uma variável e pode trazer -X")]
        found = _gh_api(api_args)
        if found is None:
            return []
        if rules := branches.policy():
            warnings, denied = _gh_api_environment(rules, api_args, cwd)
            if denied:
                return [Finding(TITLE_GITHUB, (), denial=denied)]
            if warnings:
                lines = (*warnings, *found.lines)
                alert = any(line.startswith("ATENÇÃO:") for line in warnings)
                found = Finding(found.title, lines, brief=found.brief, alert=alert)
        return [found]
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
    title = f"{program} {method} para {place or 'destino não encontrado'}"
    lines = ("Envia dados no corpo da chamada",) if data else ()
    return [Finding(title, lines, brief=title)]


def _pending_summary(folder: str, title: str, preview: str, code: str) -> Finding:
    """The box for applying the pending preview `code` kept in the store `folder`.

    `preview` is the command that makes the record. A record that is not there is denied, not
    asked: a box that cannot show what the write will do is a rubber stamp.
    """
    path = _data_dir() / folder / "pending" / f"{code}.json"
    kind = "release preview" if folder == "release" else "preview"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        where = "" if folder == "release" else " in the default store"
        return Finding(
            title,
            (),
            f"Blocked: no pending {kind} with code {code}{where}; run {preview} first.",
        )
    except (OSError, ValueError):
        return Finding(
            title,
            (),
            f"Blocked: the pending {kind} with code {code} could not be read; run {preview} again.",
        )
    summary = record.get("summary") if isinstance(record, dict) else None
    if not isinstance(summary, list) or not summary or not all(isinstance(s, str) for s in summary):
        line = f"A prévia não tem resumo; veja antes com `{preview}`"
        return Finding(title, (line,))
    return Finding(title, tuple(summary), brief=f"{title} ({len(summary)} mudanças)")


def _observe_arguments(args: list[Word]) -> tuple[list[Word], dict[str, list[Word]]]:
    """The positionals and the value flags of `ws observe run`, argparse prefixes (`--proj`)
    included; the other flags are dropped."""
    positionals: list[Word] = []
    values: dict[str, list[Word]] = {name: [] for name in OBSERVE_VALUE_FLAGS}
    index = 0
    while index < len(args):
        word = args[index]
        index += 1
        if word.text == "--":
            positionals += args[index:]
            break
        flag, equals, value = word.text.partition("=")
        names = [name for name in OBSERVE_VALUE_FLAGS if len(flag) > 2 and name.startswith(flag)]
        if len(names) != 1:
            if not word.text.startswith("-"):
                positionals.append(word)
            continue
        if equals:
            values[names[0]].append(Word(value, word.bare, word.expands))
        elif index < len(args):
            values[names[0]].append(args[index])
            index += 1
    return positionals, values


def _observe_plans(task: str, project: str | None) -> list[Path]:
    """The plan files of `task`: in `project`, or in every project as `ws observe` searches."""
    root = _data_dir() / "projects"
    if project is not None:
        path = root / project / "observations" / f"{task}.toml"
        return [path] if path.is_file() else []
    return sorted(path for path in root.glob(f"*/observations/{task}.toml") if path.is_file())


def _database_checks(path: Path) -> list[tuple[str, str]] | None:
    """(id, database) of each database check of a plan, in order; None when it cannot be read.

    Read-only, with `tomllib`: the hook never imports `ws`. The SQL never leaves this function.
    """
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_PLAN_BYTES + 1)
        if len(raw) > MAX_PLAN_BYTES:
            return None
        plan = tomllib.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    checks = plan.get("checks", [])
    if not isinstance(checks, list) or not all(isinstance(check, dict) for check in checks):
        return None
    found = []
    for check in checks:
        if check.get("kind") != "database":
            continue
        name, database = check.get("id"), check.get("database", DEFAULT_DATABASE)
        if not isinstance(name, str) or not isinstance(database, str):
            return None
        found.append((name, database))
    return found


def _changes_plan(scan: Scan, command: Command, task: str) -> str | None:
    """A word of the command line that may change the plan of `task` before the run reads it.

    A redirection to the plan, or another command that is not read-only (`cp`, `mv`, `tee`,
    `sed -i`, a script) and names the `observations` folder or `<TASK>.toml`.
    """

    def names_plan(text: str) -> bool:
        return bool(PLAN_FOLDER.search(text)) or f"{task}.toml" in text

    for each in scan.commands:
        for target in each.writes:
            if names_plan(target):
                return target
        if each is command:
            continue
        texts = [word.text for word in each.words]
        index = shell.locate_program(texts)
        program = "" if index is None else program_name(texts[index])
        args = texts if index is None else texts[index + 1 :]
        if program in HARMLESS or (program == "sed" and not any(map(SED_IN_PLACE.match, args))):
            continue
        for text in args:
            if names_plan(text):
                return text
    return None


def _observe_run(command: Command, args: list[Word], scan: Scan) -> Finding:
    """The box of `ws observe run` with `args` (the words after `run`): each database check the
    run may query, from the plan file. A plan the gate cannot find or read, or one the same
    command line may change first, asks as unsure."""
    texts = [word.text for word in command.words]
    positionals, values = _observe_arguments(args)
    if not positionals:
        return _found(TITLE_REPLICA, "Falta a tarefa; o ws vai recusar", _snippet(texts))
    task = positionals[0]
    project = values["--project"][-1] if values["--project"] else None
    if task.expands:
        reason = "A tarefa vem de uma variável ou comando; não sei o que será consultado"
        return _found(TITLE_UNSURE, reason, _snippet(texts))
    if project is not None and project.expands:
        reason = "O projeto vem de uma variável ou comando; não sei o que será consultado"
        return _found(TITLE_UNSURE, reason, _snippet(texts))
    if not TASK_REF.fullmatch(task.text):
        return _found(TITLE_REPLICA, "Tarefa inválida; o ws vai recusar", task.text)
    if project is not None and not PROJECT_SLUG.fullmatch(project.text):
        return _found(TITLE_REPLICA, "Projeto inválido; o ws vai recusar", project.text)
    if changed := _store_change(scan):
        reason = "Pode mudar a pasta de onde o ws lê o plano; não sei o que será consultado"
        return _found(TITLE_UNSURE, reason, changed)
    if changed := _changes_plan(scan, command, task.text):
        return _found(TITLE_UNSURE, "O comando muda o plano antes de rodar", changed)
    try:
        plans = _observe_plans(task.text, project.text if project else None)
    except OSError:
        plans = []
    if not plans:
        reason = f"Não achei o plano de {task.text}; não sei o que será consultado"
        return _found(TITLE_UNSURE, reason, _snippet(texts))
    title = f"{TITLE_REPLICA} ({task.text})"
    if len(plans) > 1:
        names = ", ".join(path.parents[1].name for path in plans)
        line = f"{len(plans)} planos para {task.text} ({names}); sem --project o ws recusa"
        return Finding(title, (line,), brief=title)
    checks = _database_checks(plans[0])
    if checks is None:
        reason = f"Não consegui ler o plano de {task.text}; não sei o que será consultado"
        return _found(TITLE_UNSURE, reason, _snippet(texts))
    chosen = values["--check"]
    if chosen and not any(word.expands for word in chosen):
        checks = [check for check in checks if check[0] in {word.text for word in chosen}]
    if not checks:
        return Finding(title, ("Nenhuma checagem de banco será rodada",), brief=title)
    lines = tuple(f"{cut(name, 40)} → {cut(database, 40)}" for name, database in checks)
    count = "1 checagem" if len(lines) == 1 else f"{len(lines)} checagens"
    return Finding(title, lines, brief=f"{title}: {count} de banco")


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
    action = rest[0].text
    if any(args[position].expands for position in top.positions[2:]):
        return [_unsure(texts, "A ação ou as ferramentas do catálogo vêm de uma variável")]
    effect = {
        "pass": "Libera ferramentas sem caixa",
        "ask": "Faz ferramentas pedirem aprovação",
    }.get(action, "Muda o catálogo do portão")
    reason = f"{effect} (ws gate catalog {cut(action, 20)})"
    return [_found(TITLE_PROTECTION, reason, _snippet(texts), alert=True)]


def _ws(command: Command, args: list[Word], scan: Scan) -> list[Finding]:
    """`ws` with `args`; `card apply` and `release publish|move` show the pending record,
    `observe run` the database checks of its plan."""
    texts = [word.text for word in command.words]
    top = parse_flags(args, set())
    names = [word.text for word in top.positionals[:2]]
    if any(args[position].expands for position in top.positions[:2]):
        return [_unsure(texts, "O subcomando do ws vem de uma variável ou comando")]
    if names[:1] == ["mcp-headers"]:
        return [
            _found(
                TITLE_CREDENTIAL,
                "Lê os cabeçalhos dos MCPs (ws mcp-headers)",
                _snippet(texts),
                alert=True,
            )
        ]
    if names[:1] == ["setup"]:
        checking = any(len(flag) > 2 and "--check".startswith(flag) for flag, _ in top.flags)
        if checking:
            return []
        reason = "Atualiza a cópia protegida dos hooks (ws setup)"
        return [_found(TITLE_PROTECTION, reason, _snippet(texts), alert=True)]
    if names == ["gate", "catalog"]:
        return _gate_catalog(texts, args, top)
    if names == ["observe", "run"]:
        return [_observe_run(command, args[top.positions[1] + 1 :], scan)]
    if names == ["card", "apply"]:
        kind = "card"
    elif names[:1] == ["release"] and names[1:] in (["publish"], ["move"]):
        kind = names[1]
    else:
        return []
    jira = kind == "card"
    title_fallback = TITLE_JIRA if jira else TITLE_GITHUB
    code = None
    code_expands = False
    for index, word in enumerate(args):
        flag, equals, value = word.text.partition("=")
        if len(flag) > 2 and "--approve".startswith(flag):
            if equals:
                code, code_expands = value, word.expands
            elif index + 1 < len(args):
                code, code_expands = args[index + 1].text, args[index + 1].expands
            else:
                code, code_expands = "", False
    if code is None:
        return [_found(title_fallback, "Falta o --approve; o ws vai recusar", _snippet(texts))]
    if code_expands or any(char in code for char in "?*["):
        done = "aplicado" if jira else "publicado"
        reason = f"O código vem de uma variável ou comando; não sei o que será {done}"
        return [_found(TITLE_UNSURE, reason, _snippet(texts))]
    if not APPROVE_CODE.fullmatch(code):
        return [_found(title_fallback, "Código de aprovação inválido; o ws vai recusar", code)]
    if changed := _store_change(scan):
        reason = "Pode mudar a pasta de onde o ws lê a prévia; não sei o que será aplicado"
        return [_found(TITLE_UNSURE, reason, changed)]
    if jira:
        title = f"Aplica a prévia {code} no Jira"
        return [_pending_summary("cards", title, "ws card preview", code)]
    if kind == "publish":
        title = f"Publica a prévia {code} no GitHub"
    else:
        title = f"Move a release (prévia {code}) no GitHub"
    return [_pending_summary("release", title, f"ws release preview {kind}", code)]


def _python_stdin_problem(command: Command, args: list[Word], program: shell.PythonProgram) -> str:
    """Why the code a Python reads from stdin cannot be read here, or an empty string."""
    if program.procsub or any(word.text.startswith("<(") for word in args):
        return "O Python recebe o código por substituição de processo"
    if command.piped:
        return "O Python recebe o código por pipe"
    if any(read != "/dev/null" for read in command.reads):
        return "O Python recebe o código de um arquivo"
    if command.here_string is not None and command.here_string_expands:
        return "O código do Python vem de uma variável ou comando"
    return ""


def _folders_walked(cwd: str, scan: Scan) -> list[str]:
    """The cwd and each folder the `cd` commands lead to, relative ones joined in order."""
    current = cwd or "/"
    found = [current]
    for folder in _entered_folders(scan):
        current = posixpath.join(current, folder)
        found.append(current)
    return found


def _script_place(word: Word, cwd: str, scan: Scan) -> str:
    """Why a script path may be stdin: `//dev/stdin`, `../../dev/stdin`, `stdin` after `cd /dev`."""
    text = word.text
    places = (
        [text]
        if text.startswith("/")
        else [posixpath.join(folder, text) for folder in _folders_walked(cwd, scan)]
    )
    if any(shell.stdin_path(place) for place in places):
        return "O Python roda um arquivo de /dev ou /proc, que pode ser a entrada padrão"
    return ""


def _program_arguments(
    command: Command, program: shell.PythonProgram, cwd: str, scan: Scan
) -> list[Finding]:
    """The program's own arguments as `ws` ones when they read a write, whatever the code says.

    `_ws`, not `_invocation`: a `$FILE` among the arguments of a script is not obfuscation. An
    argument that holds a whole `ws` write (`os.system(sys.argv[1])`) is judged as a command line.
    """
    args = list(program.args)
    texts = [word.text for word in args]
    code = program.word.text if program.kind == "code" and program.word else ""
    changed = ENVIRONMENT.search(code) or _store_change(scan)
    found = [
        finding
        for text in texts
        if len(text.split()) > 1 and WS_WORD.search(text) and WRITE_WORDS.search(text)
        for finding in _text_findings(("env " if changed else "") + text, cwd, scan.depth + 1)
    ]
    for index in range(len(texts) - 1):
        if (texts[index], texts[index + 1]) in WS_WRITES:
            return found + _ws(command, args[index:] + args[:index], scan)
    return found


def _mentions_ws(program: shell.PythonProgram, scan: Scan) -> bool:
    """The `-c` code, or the code read from stdin, names `ws`."""
    if program.kind == "code" and program.word is not None:
        return bool(WS_WORD.search(shell.python_source(program.word.text)))
    return program.kind == "stdin" and any(WS_WORD.search(code) for code in scan.scripts)


def _python_program_findings(
    command: Command,
    program: shell.PythonProgram,
    cwd: str,
    scan: Scan,
    args: list[Word],
) -> list[Finding]:
    """One program a Python command line runs; `args` are the words after `python` or `uv`."""
    texts = [word.text for word in command.words]
    word = program.word
    if program.kind == "unknown":
        return [_unsure(texts, "Opção do Python que não conheço")]
    place = _script_place(word, cwd, scan) if program.kind == "script" and word else ""
    if place:
        return [_unsure(texts, place)]
    if program.kind == "code" and word is not None and word.expands:
        return [_unsure(texts, "O código do Python vem de uma variável ou comando")]
    if program.kind == "module" and word is not None and word.expands:
        return [_unsure(texts, "O módulo do Python vem de uma variável ou comando")]
    inspect = shell.inspect_variable(scan.commands)
    if shell.reads_stdin_code(program, inspect) and (
        problem := _python_stdin_problem(command, args, program)
    ):
        return [_unsure(texts, problem)]
    module = word.text if program.kind == "module" and word is not None else ""
    found = []
    if module in WS_MODULES:
        found += _invocation(command, "ws", list(program.args), cwd, scan)
    elif module.startswith("ws."):
        if module.count(".") > 1:
            return [_unsure(texts, "Módulo do ws chamado direto; não sei o que será feito")]
        found += _invocation(command, "ws", [Word(module.split(".")[1]), *program.args], cwd, scan)
    elif _mentions_ws(program, scan):
        found += _ws(command, list(program.args), scan)
    return found + _program_arguments(command, program, cwd, scan)


def _python_findings(
    command: Command, name: str, args: list[Word], cwd: str, scan: Scan
) -> list[Finding]:
    return [
        finding
        for program in shell.python_programs(name, args)
        for finding in _python_program_findings(command, program, cwd, scan, args)
    ]


def _reads_unseen_commands(command: Command, name: str, args: list[Word]) -> str | None:
    """Why a shell or `eval` runs text the gate cannot read, or None."""
    if name == "eval":
        code = args
    elif name in shell.SHELLS:
        script = shell.script_word(args)
        if script is None and (command.piped or command.reads_file):
            if all(word.text.startswith("-") for word in args):
                return "Os comandos chegam ao shell por pipe ou arquivo"
        code = [script] if script else []
    else:
        return None
    if code and code[0].expands and code[0].text.lstrip().startswith(("$", "`")):
        return "O script vem de uma variável ou comando"
    return None


def _invocation(
    command: Command, name: str, args: list[Word], cwd: str, scan: Scan
) -> list[Finding]:
    texts = [word.text for word in command.words]
    if reason := _reads_unseen_commands(command, name, args):
        return [_unsure(texts, reason)]
    if shell.PYTHON.fullmatch(name) or name == "uv":
        return _python_findings(command, name, args, cwd, scan)
    if name not in WATCHED:
        return []
    if name in ("curl", "wget", "ws") and any(word.bare for word in args):
        return [_unsure(texts, "Tem $, crase ou chaves fora de aspas")]
    if name == "git":
        return _git(command, args, cwd, scan)
    if name == "gh":
        return _gh(command, args, cwd)
    if name == "ws":
        return _ws(command, args, scan)
    return _http(name, args)


def _python_code(command: Command) -> set[int]:
    """Positions of the `-c` code of a Python and of the options before it.

    `_script_findings` judges the code, so the path it cites is not a write. The words after the
    code are the program's own arguments (`--out=~/.claude/settings.json`) and are judged as paths.
    """
    found = set()
    for name, words in shell.invocations(command):
        if not shell.PYTHON.fullmatch(name):
            continue
        program = shell.parse_python(words)
        if program.kind != "code":
            continue
        start = len(command.words) - len(words)
        for position in range(start, start + len(words) - len(program.args)):
            word = command.words[position]
            if word.text.startswith("-") or word is program.word:
                found.add(position)
    return found


def _protection(command: Command) -> list[Finding]:
    texts = [word.text for word in command.words]
    index = shell.locate_program(texts)
    program = "" if index is None else program_name(texts[index])
    first = 0 if index is None else index + 1
    args = texts[first:]
    if program in READ_ONLY | NAVIGATION:
        args = []
    elif program == "git" and next((t for t in args if not t.startswith("-")), "") in READ_ONLY_GIT:
        args = []
    hits = [path for path in command.writes if PROTECTED_PATH.search(path)]
    code = _python_code(command)
    for position, text in enumerate(args, start=first):
        if position in code:
            continue
        if " " not in text and PROTECTED_PATH.search(text):
            hits.append(text)
        elif INTERPRETERS.fullmatch(program) and PROTECTED_IN_CODE.search(text):
            hits.append(text)
    if not hits:
        return []
    return [_found(TITLE_PROTECTION, "Mexe num arquivo de proteção", _pretty(hits[0]), alert=True)]


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
                _found(
                    TITLE_PROTECTION,
                    f"Roda dentro de {cut(_pretty(entered), 40)}",
                    _snippet(command),
                    alert=True,
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
        os.path.normpath(home / ".claude" / ".credentials.json"),
        os.path.normpath(home / ".git-credentials"),
    }


def _credential_path(text: str, folder: str | None = None, recursive: bool = False) -> str | None:
    """The credential a path-like word names, or None.

    Covers the credentials file of `ws`, the `gh` hosts file, Claude Code's `.credentials.json`,
    `~/.git-credentials`, the `~/.ssh` private keys (`id_*` but not `.pub`), those folders
    themselves (a copy or an archive reads what is inside) and a glob that could match them.
    Brace expansions are opened by the caller (`_brace_words`). `folder` is the cwd or one the
    command entered with `cd`: a relative path is then looked up in it. `recursive`: the program
    reads whole trees (`grep -r`, `tar`, `cp -r`), so `/`, `/home`, the home, `~/.config` and
    `~/.claude` count too.
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
    parents = (home, f"{home}/.config", f"{home}/.claude", os.path.dirname(home))
    if recursive and (PARENT_FOLDER.search(text) or expanded in parents):
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
    reason = f"Usa o ajudante de credenciais (git {cut(verb, 30)})"
    return _found(TITLE_CREDENTIAL, reason, _snippet(texts), alert=True)


def _brace_words(text: str) -> list[str]:
    """The words a brace expansion gives (`id_{rsa,x}`); a range or too many become a glob `*`."""
    pending, done = [text], []
    while pending:
        current = pending.pop()
        found = shell.BRACE_EXPANSION.search(current)
        if found is None:
            done.append(current)
            continue
        inner = found.group()[1:-1]
        if "," not in inner or len(pending) + len(done) >= MAX_BRACE_WORDS:
            while shell.BRACE_EXPANSION.search(current):
                current = shell.BRACE_EXPANSION.sub("*", current)
            pending.append(current)
            continue
        head, tail = current[: found.start()], current[found.end() :]
        pending += [head + choice + tail for choice in inner.split(",")]
    return done


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
                (
                    p
                    for each in _brace_words(text)
                    for f in (None, *folders)
                    if (p := _credential_path(each, f, recursive))
                ),
                None,
            )
            hits += [path] if path else []
    if not hits:
        return []
    return [_found(TITLE_CREDENTIAL, "Lê um arquivo de credencial", _pretty(hits[0]), alert=True)]


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
        return [_unsure(texts, "O programa vem de uma variável", TITLE_UNSURE_PROGRAM)]
    if not NAMES.search(whole):
        return []
    reason = "O programa vem de uma variável e o comando cita ws, gh, git…"
    return [_unsure(texts, reason, TITLE_UNSURE_PROGRAM)]


def _names_watched_program(text: str) -> bool:
    name = program_name(text)
    return name in WATCHED and (text == name or text.endswith("/bin/" + name))


def _runner_positions(command: Command, index: int) -> range:
    """Positions of the words a runner module (`python3 -m runpy ws ...`) runs as a program:
    `_python_findings` judges each one, so they are not hidden."""
    program = shell.parse_python(command.words[index + 1 :])
    if program.kind != "module" or program.word is None:
        return range(0)
    if program.word.text not in shell.RUNNER_MODULES:
        return range(0)
    start = len(command.words) - len(program.args)
    return range(start, start + shell.runner_word_positions(program))


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
    judged = _runner_positions(command, index) if shell.PYTHON.fullmatch(program) else range(0)
    for position, text in enumerate(texts[1:], start=1):
        if position == index or not _names_watched_program(text):
            continue
        if (shell.PYTHON.fullmatch(program) and texts[position - 1] == "-m") or position in judged:
            continue
        return [
            _unsure(texts, f"{cut(program, 20)} pode rodar {cut(text, 20)}, que vem como argumento")
        ]
    return []


def _wrapper_script_by_expansion(command: Command) -> list[Finding]:
    for script in shell.wrapper_scripts(command.words):
        if script.expands and script.text.lstrip().startswith(("$", "`")):
            texts = [word.text for word in command.words]
            return [_unsure(texts, "O script vem de uma variável ou comando")]
    return []


def _applies_card(code: str) -> bool:
    """Python that may apply a card preview: it names `run_apply`, or imports `ws` and names
    `card` and `apply`."""
    if "run_apply" in code:
        return True
    return bool(WS_IMPORT.search(code)) and "card" in code and "apply" in code


RELEASE_WRITE_NAME = re.compile(r"(?<![A-Za-z])(?:run_publish|run_move)")
RELEASE_WRITE_WORD = re.compile(r"(?<![A-Za-z])(?:publish|move)")
RELEASE_WORD = re.compile(r"(?<![A-Za-z])release")
REPLICA_QUERY_NAME = re.compile(r"(?<![A-Za-z])(?:run_day|scalar_text|open_database|_query)")
OBSERVE_WORD = re.compile(r"(?<![A-Za-z])observe(?![A-Za-z])")
RUN_WORD = re.compile(r"(?<![A-Za-z])run(?![A-Za-z])")
DATABASE_WORD = re.compile(r"(?<![A-Za-z])database")
SCALAR_WORD = re.compile(r"(?<![A-Za-z])scalar")
# `exec`, `eval` and `compile` count only as bare names: `re.compile(...)` and `m.eval()` are
# methods of other objects.
BARE_DYNAMIC = r"(?<![.\w])(?:exec|eval|compile)\b"
# Without `ws` in the code, only a call or a handed-over name counts: `print('compile done')`
# names no function.
BARE_CALL = re.compile(r"(?<![.\w'\"])(?:exec|eval|compile)\s*(?=\()")
BARE_ALIAS = re.compile(r"[=(,]\s*(?:exec|eval|compile)\s*(?:[,);\n]|$)")
DYNAMIC_NAMES = re.compile(
    r"\b(?:getattr|import_module|importlib|__import__|runpy|vars|__dict__|attrgetter|globals"
    r"|locals|pkgutil|pydoc|pickle|marshal|builtins|__builtins__)\b|" + BARE_DYNAMIC
)
MAIN_WITH_ARGUMENTS = re.compile(r"\bmain\s*\(\s*[^)\s]|\bws\.cli\b[^;\n]*\(\s*[^)\s]")
CLI_IMPORT = re.compile(
    r"\bfrom\s+ws\.cli\s+import\b|\bimport\s+ws\.cli\b|\bfrom\s+ws\s+import\b[^;\n]*\bcli\b"
)
# `print(build_parser().format_help())`: `print` hands nothing to the ws.
CALL_WITH_ARGUMENTS = re.compile(r"(?:(?<=\w)(?<!\bprint)|(?<=[)\]]))\s*\(\s*[^)\s]")
CLI_CALLS = re.compile(r"\b(?:parse_args|parse_known_args|parse_intermixed_args)\b|\.handler\b")
SYS_ARGV = re.compile(r"\bsys\.argv\b|\bargv\b")
IMPORT_CALLS = ("__import__", "import_module", "run_module", "run_path", "resolve_name")
# Without `ws` in the code; `pickle` counts only with it (its opcodes are out of reach).
DYNAMIC_MODULES = (
    "importlib",
    "runpy",
    "pkgutil",
    "pydoc",
    "marshal",
    "builtins",
    "__builtins__",
)
DYNAMIC_IMPORT_FROM = re.compile(r"\bfrom\s+(?:pkgutil|pydoc|marshal|builtins)\s+import\b")
# Uses of those modules that import or run nothing: listing modules, looking at a module.
LISTS_MODULES = re.compile(r"\.(?:iter_modules|extend_path)\s*\(")
LOOKS_AT = re.compile(r"\b(?:dir|help|repr|type|print)\s*\(\s*$")
CLOSING = re.compile(r"\s*\)")
LITERAL = r"""[rbuRBU]{0,2}(?:'(?!ws)[^'\\]*'|"(?!ws)[^"\\]*")"""
LITERAL_CALL = re.compile(rf"\s*\(\s*(?:\)|{LITERAL}\s*[,)])")
MODULE_LITERAL_CALL = re.compile(rf"(?:\.\w+)+{LITERAL_CALL.pattern}")
CODE_STRING_CALL = re.compile(r"(?<![\w])timeit\s*(?=\()")
RUNS_PROGRAMS = re.compile(r"\b(?:subprocess|os|pty|asyncio)\b")
RUNNER_FUNCTIONS = {
    "subprocess": frozenset(
        "run call check_call check_output Popen getoutput getstatusoutput".split()
    ),
    "os": frozenset(
        "system popen execl execle execlp execlpe execv execve execvp execvpe spawnl spawnle "
        "spawnlp spawnlpe spawnv spawnve spawnvp spawnvpe posix_spawn posix_spawnp".split()
    ),
    "pty": frozenset({"spawn"}),
    "asyncio": frozenset({"create_subprocess_exec", "create_subprocess_shell"}),
}
ENVIRONMENT = re.compile(r"\benviron\b|\bputenv\b")
MAX_CODE_DEPTH = 3


def _writes_release(code: str) -> bool:
    """Python that may publish or move a release: it names `run_publish` or `run_move`, or
    imports `ws` and names `release` with `publish` or `move`."""
    if RELEASE_WRITE_NAME.search(code):
        return True
    return (
        bool(WS_IMPORT.search(code))
        and bool(RELEASE_WORD.search(code))
        and bool(RELEASE_WRITE_WORD.search(code))
    )


def _queries_replica(code: str) -> bool:
    """Python that may query a database: it names `run_day`, `scalar_text`, `open_database` or
    `_query`, or imports `ws` and names `observe` with `run` or `database` with `scalar`."""
    if REPLICA_QUERY_NAME.search(code):
        return True
    if not WS_IMPORT.search(code):
        return False
    observe = OBSERVE_WORD.search(code) and RUN_WORD.search(code)
    return bool(observe or (DATABASE_WORD.search(code) and SCALAR_WORD.search(code)))


def _in_import(code: str, start: int) -> bool:
    """The name at `start` sits in an `import` or `from ... import` statement."""
    begin = max(code.rfind("\n", 0, start), code.rfind(";", 0, start)) + 1
    return code[begin:start].lstrip().startswith(("import ", "from "))


def _runs_built_code(code: str) -> bool:
    """Python that imports or runs code by a name or text that is not a plain literal.

    The first argument of the call must be a literal that does not start with `ws`: `exec('x')`,
    `importlib.import_module('json')` and `importlib.metadata.version('pytest')` pass.
    """
    for name in IMPORT_CALLS:
        for found in re.finditer(rf"\b{name}\b", code):
            if not LITERAL_CALL.match(code, found.end()):
                return True
    for found in BARE_CALL.finditer(code):
        if not LITERAL_CALL.match(code, found.end()):
            return True
    if BARE_ALIAS.search(code):
        return True
    for found in CODE_STRING_CALL.finditer(code):
        if not LITERAL_CALL.match(code, found.end()):
            return True
    for name in DYNAMIC_MODULES:
        for found in re.finditer(rf"\b{name}\b", code):
            if not _in_import(code, found.start()) and not _plain_module_use(code, found):
                return True
    return bool(DYNAMIC_IMPORT_FROM.search(code))


def _plain_module_use(code: str, found: re.Match[str]) -> bool:
    """`module.attr('literal')`, `pkgutil.iter_modules(...)` or `dir(module)`."""
    if MODULE_LITERAL_CALL.match(code, found.end()) or LISTS_MODULES.match(code, found.end()):
        return True
    closed = CLOSING.match(code, found.end())
    return bool(closed and LOOKS_AT.search(code, 0, found.start()))


def _dynamic_reason(code: str) -> str:
    """Why the gate cannot follow what the code runs, or an empty string."""
    ws = WS_WORD.search(code)
    if ws and (
        MAIN_WITH_ARGUMENTS.search(code)
        or CLI_CALLS.search(code)
        or (CLI_IMPORT.search(code) and CALL_WITH_ARGUMENTS.search(code))
    ):
        return "Python que chama o main ou o parser do ws com argumentos"
    if ws and (DYNAMIC_NAMES.search(code) or SYS_ARGV.search(code)):
        return "Python que chama o ws com nomes montados na execução"
    if _runs_built_code(code):
        return "Python que monta nomes ou código na execução; não sei o que ele roda"
    return ""


def _runner_names(tree: ast.AST) -> tuple[dict[str, str], dict[str, str]]:
    """Names that stand for `subprocess`, `os`, `pty`, `asyncio`, and for their run functions."""
    modules = {name: name for name in RUNNER_FUNCTIONS}
    functions: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in RUNNER_FUNCTIONS:
                    modules[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in RUNNER_FUNCTIONS:
            module = node.module
            for alias in node.names:
                if alias.name == "*":
                    functions.update(
                        {name: f"{module}.{name}" for name in RUNNER_FUNCTIONS[module]}
                    )
                elif alias.name in RUNNER_FUNCTIONS[module]:
                    functions[alias.asname or alias.name] = f"{module}.{alias.name}"
    return modules, functions


def _runner_function(node: ast.expr, modules: dict[str, str], functions: dict[str, str]) -> str:
    """`module.function` for a call of a function that runs a program, or an empty string."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        module = modules.get(node.value.id)
        if module and node.attr in RUNNER_FUNCTIONS[module]:
            return f"{module}.{node.attr}"
        return ""
    return functions.get(node.id, "") if isinstance(node, ast.Name) else ""


def _call_command(call: ast.Call, function: str) -> tuple[str, bool, bool]:
    """The command line a call runs, from its literal arguments; whether every argument is a
    literal; and whether it passes its own environment."""
    args = list(call.args) + [keyword.value for keyword in call.keywords if keyword.arg == "args"]
    env = any(keyword.arg == "env" for keyword in call.keywords)
    launches = function.startswith(("os.exec", "os.spawn", "os.posix_spawn"))
    if function.startswith("os.posix_spawn"):
        env, args = True, args[:2]
    elif launches and function.endswith("e"):
        env, args = True, args[:-1]
    if function.startswith("os.spawn"):
        args = args[1:]
    words: list[str] = []
    literal = True
    for arg in args:
        items = arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]
        for item in items:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                words.append(item.value)
            elif not isinstance(item, ast.Constant):
                literal = False
    if len(words) == 1 and not launches:
        return words[0], literal, env
    if launches:
        # exec and spawn take the path, then an argv whose first word is only the name shown.
        words = words[:1] + words[2:]
    return shlex.join(words), literal, env


def _program_runs(code: str, scan: Scan, cwd: str, depth: int) -> tuple[list[Finding], bool]:
    """What the code's `subprocess`, `os.system`, `os.exec*`, `os.spawn*` and `pty.spawn` calls run.

    A literal command that names `ws` is judged like a command line. Returns the findings and
    whether the code cites `ws` and runs a program the gate cannot read.
    """
    if not RUNS_PROGRAMS.search(code):
        return [], False
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return [], bool(WS_WORD.search(code))
    modules, functions = _runner_names(tree)
    found: list[Finding] = []
    opaque = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = _runner_function(node.func, modules, functions)
        if not function:
            continue
        text, literal, env = _call_command(node, function)
        if not literal:
            opaque = True
            continue
        if not WS_WORD.search(text):
            continue
        # `env` makes the store a variable for `_ws`, which then cannot name the record.
        changed = env or ENVIRONMENT.search(code) or _store_change(scan)
        found += _text_findings(("env " if changed else "") + text, cwd, depth + 1)
    return found, opaque and bool(WS_WORD.search(code))


def _code_findings(code: str, scan: Scan, cwd: str, depth: int) -> list[Finding]:
    found, opaque = _program_runs(code, scan, cwd, depth)
    writes = []
    if _writes_release(code):
        reason = "Python que chama o ws e pode publicar ou mover uma release"
        writes.append(_found(TITLE_GITHUB, reason, code))
    if _applies_card(code):
        writes.append(_found(TITLE_JIRA, "Python que chama o ws e pode aplicar uma prévia", code))
    if _queries_replica(code):
        reason = "Python que chama o ws e pode consultar a réplica"
        writes.append(_found(TITLE_REPLICA, reason, code))
    if not writes:
        reason = _dynamic_reason(code)
        if not reason and opaque:
            reason = "Python que roda um programa com argumentos montados e cita o ws"
        if reason:
            found.append(_found(TITLE_UNSURE, reason, code))
    return found + writes


def _script_findings(scan: Scan, cwd: str, depth: int) -> list[Finding]:
    found = [
        _found(TITLE_UNSURE, "Python com código que vem de uma expansão", body)
        for body in scan.opaque_python
    ]
    for code in dict.fromkeys(scan.scripts):
        found += _code_findings(code, scan, cwd, depth)
        if reading := _credential_in_code(code):
            found.append(
                _found(TITLE_CREDENTIAL, "Python que cita um arquivo de credencial", reading, True)
            )
        if PROTECTED_IN_CODE.search(code) and CODE_WRITES.search(code):
            found.append(
                _found(
                    TITLE_PROTECTION, "Python que grava e cita settings ou hooks", code, alert=True
                )
            )
    return found


def _combine(findings: list[Finding]) -> Decision:
    unique = list(dict.fromkeys(findings))
    if not unique:
        return PASS
    if denial := next((finding.denial for finding in unique if finding.denial), None):
        return deny(denial)
    groups: dict[tuple[str, str, bool], list[Finding]] = {}
    for finding in unique:
        groups.setdefault(finding.key(), []).append(finding)
    if len(groups) == 1:
        group = next(iter(groups.values()))
        if len(group) == 1:
            return ask(group[0].title, list(group[0].lines))
        return ask(group[0].title, group[0].compact(len(group)))
    titles = {group[0].title for group in groups.values()}
    title = titles.pop() if len(titles) == 1 else f"{len(groups)} pedidos neste comando"
    lines = [line for group in groups.values() for line in group[0].compact(len(group))]
    return ask(title, lines)


def _decide_text(command: str, cwd: str) -> Decision:
    # Checked before any parser or regex runs: a huge word could make them slow past the deadline.
    if any(len(part) > MAX_WORD for part in command.split()):
        return ask(TITLE_UNSURE, ["Uma palavra do comando passa de 4 KB; não a leio"])
    return _combine(_text_findings(command, cwd))


def _text_findings(command: str, cwd: str, depth: int = 0) -> list[Finding]:
    """Everything a command line asks for; `depth` counts command lines found inside Python."""
    if depth > MAX_CODE_DEPTH or any(len(part) > MAX_WORD for part in command.split()):
        return [_found(TITLE_UNSURE, "Python que roda comandos que não consigo ler", command)]
    scan = shell.scan(command)
    scan.depth = depth
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
    findings += _script_findings(scan, cwd, depth)
    if scan.overrun:
        findings.append(
            _found(TITLE_UNSURE, "É grande ou aninhado demais para ler a tempo", command)
        )
    elif scan.unparsed and NAMES.search(command):
        findings.append(
            _found(
                TITLE_UNSURE,
                "Aspas ou parênteses que não consegui ler; cita ws, gh, git, curl ou wget",
                command,
            )
        )
    return findings


def decide(command: str, cwd: str) -> Decision:
    """The decision for a command, judged on each text `variables.worlds` resolves it to.

    The strictest wins (deny, then ask, then pass); an ask keeps the box of the first text that
    asks, which is the one with every value when that one asks.
    """
    # Checked before any parser or regex runs: a huge word could make them slow past the deadline.
    if any(len(part) > MAX_WORD for part in command.split()):
        return _decide_text(command, cwd)
    chosen = PASS
    for text in variables.worlds(command):
        decision = _decide_text(text, cwd)
        if decision.kind == "deny":
            return decision
        if decision.kind == "ask" and chosen.kind == "pass":
            chosen = decision
    return chosen
