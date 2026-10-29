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

Text rules cannot see a script file the command runs, text piped to `python` or `node`, programs
that start other programs (`xargs`, `find -exec`, `ssh`) or a `cwd` that Claude Code reports stale.
"""

import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from . import shell
from .decision import PASS, Decision, ask, body_summary, cut
from .shell import Command, Scan, Word, program_name

TITLE_GITHUB = "Gravar fora — GitHub"
TITLE_JIRA = "Gravar fora — Jira"
TITLE_HTTP = "Gravar fora — HTTP"
TITLE_PROTECTION = "Proteção do Claude Code"
TITLE_UNSURE = "Comando não lido com certeza"
TITLE_REMOTE = "Destino do git push"

WATCHED = {"git", "gh", "curl", "wget", "ws"}
NAMES = re.compile(r"\b(?:ws|gh|git|curl|wget)\b")
APPROVE_CODE = re.compile(r"[0-9a-f]{12}")
WS_BY_CODE = re.compile(r"\bfrom\s+ws\b|\bimport\s+ws\b|\bws\.card\b|run_apply")
GIT_DIRECTORY_VARIABLE = re.compile(r"GIT_(?:DIR|WORK_TREE|COMMON_DIR|INDEX_FILE)=")

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

GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix"}
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
    title: str
    lines: tuple[str, ...]


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
    return Finding(TITLE_UNSURE, (reason, _line(texts), "Confira o comando antes de aprovar."))


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


def _changes_directory(scan: Scan) -> bool:
    for command in scan.commands:
        for name, _ in shell.invocations(command)[:1]:
            if name in NAVIGATION:
                return True
        for word in command.words:
            text = word.text
            if text == "-C" or text.startswith(("--git-dir", "--work-tree")):
                return True
            if GIT_DIRECTORY_VARIABLE.match(text):
                return True
    return False


def _split_git(args: list[Word]) -> tuple[list[str], int | None]:
    """The `-C` directories and the index of the subcommand among the arguments."""
    directories: list[str] = []
    index = 0
    while index < len(args) and args[index].text.startswith("-"):
        option = args[index].text
        index += 1
        if option in GIT_VALUE_OPTIONS and index < len(args):
            if option == "-C":
                directories.append(args[index].text)
            index += 1
    return directories, index if index < len(args) else None


def _folder(cwd: str, directories: list[str]) -> str:
    folder = cwd or "."
    for directory in directories:
        folder = os.path.normpath(os.path.join(folder, os.path.expanduser(directory)))
    return folder


def _push(rest: list[Word], directories: list[str], cwd: str, moved: bool) -> Finding:
    parsed = parse_flags(rest, PUSH_VALUE_FLAGS)
    names = [word.text for word in parsed.positionals]
    remote = parsed.value("--repo")
    if remote is None and names:
        remote, names = names[0], names[1:]
    forced = [name for name, _ in parsed.flags if name.startswith(FORCE_FLAGS)]
    forced += ["+" + spec[1:] for spec in names if spec.startswith("+")]
    deleted = parsed.has("--delete", "-d") or any(spec.startswith(":") for spec in names)
    lines = [
        f"Enviar commits (git push) da pasta {_pretty(_folder(cwd, directories))}",
        f"Remoto: {remote or 'o padrão do repositório'}",
        f"Referências: {', '.join(names) if names else 'as configuradas no repositório'}",
    ]
    if forced:
        lines.append(f"ATENÇÃO: {forced[0]} força o envio e pode reescrever o histórico do remoto")
    if deleted:
        lines.append("ATENÇÃO: apaga referências no remoto")
    extra = [name for name, _ in parsed.flags if name in ("--tags", "--all", "--mirror", "--prune")]
    if extra:
        lines.append("Opções: " + " ".join(extra))
    if moved:
        lines.append("Atenção: o comando muda de pasta; confira se é a pasta acima")
    return Finding(TITLE_GITHUB, tuple(lines))


def _git(command: Command, args: list[Word], cwd: str, scan: Scan) -> list[Finding]:
    texts = [word.text for word in command.words]
    directories, verb_index = _split_git(args)
    if verb_index is None:
        return []
    if any(word.expands for word in args[: verb_index + 1]):
        return [_unsure(texts, "O subcomando do git vem de uma expansão (variável ou comando).")]
    verb, rest = args[verb_index].text, args[verb_index + 1 :]
    if verb == "push":
        quiet = texts in (["git", "push"], ["git", "push", "origin", "main"])
        if quiet and not _changes_directory(scan) and _listed_for_push(cwd):
            return []
        return [_push(rest, directories, cwd, _changes_directory(scan))]
    if verb == "remote":
        action = next((w.text for w in rest if not w.text.startswith("-")), "")
        if action in REMOTE_CHANGES:
            return [
                Finding(
                    TITLE_REMOTE,
                    (f"Muda os remotos do repositório (git remote {action})", _line(texts)),
                )
            ]
    if verb == "config":
        parsed = parse_flags(rest, set())
        names = [word.text for word in parsed.positionals]
        reading = any(flag in CONFIG_READS for flag, _ in parsed.flags) or names[:1] in (
            ["get"],
            ["list"],
        )
        key = next((name for name in names if REMOTE_KEYS.match(name)), None)
        if key and not reading:
            return [
                Finding(
                    TITLE_REMOTE,
                    (f"Muda a configuração do git que decide o destino: {key}", _line(texts)),
                )
            ]
    return []


def _gh_repo(parsed: Parsed, cwd: str) -> str:
    repo = parsed.value("-R", "--repo")
    if repo:
        return repo
    return f"{_pretty(cwd)} (pasta atual)" if cwd else "o repositório atual"


def _gh_body(parsed: Parsed) -> str | None:
    body = parsed.value("-b", "--body")
    if body is not None:
        return body_summary(body)
    name = parsed.value("-F", "--body-file")
    return None if name is None else f"arquivo {name}"


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
        if _graphql_is_read(fields, cwd):
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


def _gh_change(group: str, action: str, tail: list[Word], cwd: str, texts: list[str]) -> Finding:
    values = GH_MERGE_VALUES if (group, action) == ("pr", "merge") else GH_CHANGE_VALUES
    parsed = parse_flags(tail, values)
    target = parsed.positionals[0].text if parsed.positionals else None
    repo = _gh_repo(parsed, cwd)
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
    return Finding(TITLE_GITHUB, tuple(lines))


def _gh(command: Command, args: list[Word], cwd: str) -> list[Finding]:
    texts = [word.text for word in command.words]
    top = parse_flags(args, GH_GLOBAL_VALUES)
    if not top.positionals:
        return []
    if any(args[position].expands for position in top.positions[:2]):
        return [_unsure(texts, "O subcomando do gh vem de uma expansão (variável ou comando).")]
    group = top.positionals[0].text
    action = top.positionals[1].text if len(top.positionals) > 1 else ""
    if group in GH_ANY_ACTION or action in GH_READS.get(group, set()):
        return []
    if group == "api":
        found = _gh_api(args[top.positions[0] + 1 :], cwd)
        return [found] if found else []
    rest = args[top.positions[1] + 1 :] if action else []
    return [_gh_change(group, action, rest, cwd, [word.text for word in args])]


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
    return [Finding(TITLE_HTTP, tuple(lines))]


def _pending_summary(code: str) -> list[str]:
    path = _data_dir() / "cards" / "pending" / f"{code}.json"
    missing = [f"Sem prévia pendente com o código {code}; o ws card apply vai recusar"]
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return missing
    except (OSError, ValueError):
        return [f"A prévia {code} existe mas não consegui ler; o ws card apply pode recusar"]
    summary = record.get("summary") if isinstance(record, dict) else None
    if not isinstance(summary, list) or not summary or not all(isinstance(s, str) for s in summary):
        return [f"A prévia {code} não tem resumo; confira com `ws card preview` antes de aprovar"]
    return [f"Aplicar a prévia {code}:", *summary]


def _ws(command: Command, args: list[Word]) -> list[Finding]:
    texts = [word.text for word in command.words]
    top = parse_flags(args, set())
    names = [word.text for word in top.positionals[:2]]
    if any(args[position].expands for position in top.positions[:2]):
        return [_unsure(texts, "O subcomando do ws vem de uma expansão (variável ou comando).")]
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
    else:
        lines = _pending_summary(code)
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
    if any(word.bare for word in args):
        return [_unsure(texts, "Tem $, crase ou chaves fora de aspas; não sei o que vai rodar.")]
    if name == "git":
        return _git(command, args, cwd, scan)
    if name == "gh":
        return _gh(command, args, cwd)
    if name == "ws":
        return _ws(command, args)
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


def _program_by_expansion(command: Command, whole: str) -> list[Finding]:
    texts = [word.text for word in command.words]
    index = shell.locate_program(texts)
    if index is None or not command.words[index].expands or not NAMES.search(whole):
        return []
    return [_unsure(texts, "O nome do programa vem de uma expansão e o comando cita ws, gh, git…")]


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
    if len(unique) == 1:
        return ask(unique[0].title, list(unique[0].lines))
    titles = {finding.title for finding in unique}
    lines: list[str] = []
    for finding in unique:
        lines += finding.lines if len(titles) == 1 else [f"— {finding.title}", *finding.lines]
    return ask(titles.pop() if len(titles) == 1 else "Vários comandos pedem aprovação", lines)


def decide(command: str, cwd: str) -> Decision:
    scan = shell.scan(command)
    findings: list[Finding] = []
    for each in scan.commands:
        findings += _protection(each)
        findings += _program_by_expansion(each, command)
        for name, args in shell.invocations(each):
            findings += _invocation(each, name, args, cwd, scan)
    findings += _after_entering_protection(scan)
    findings += _script_findings(scan)
    if scan.unparsed and NAMES.search(command):
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
