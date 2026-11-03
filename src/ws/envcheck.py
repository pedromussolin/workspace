"""Which env var names a repo reads, against the Parameter Store and argocd (`ws env check`).

Names only. A value from the store never gets here: the sources keep the text before the first
`=` of a line and drop the rest at once, and no message built here quotes a command's output.
"""

import ast
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

MAX_WHERE = 3
KIND_ORDER = {"settings": 0, "dynamic": 1, "helper": 2, "shell": 3, "migration": 4}
SETTINGS_BASE = "BaseSettings"
SETTINGS_CONFIG_KEY = "env_prefix"
ALIAS_KEYS = ("validation_alias", "alias")
REGULAR_MODES = ("100644", "100755")


class SetupError(Exception):
    """Config, credentials or the commit are not in place: exit 2."""


@dataclass(frozen=True)
class CodeName:
    name: str
    required: bool
    kind: str  # settings | helper | dynamic | migration | shell
    where: tuple[str, ...]  # "path:line", at most MAX_WHERE kept, plus `count`
    count: int


@dataclass(frozen=True)
class Unresolved:
    where: str
    call: str


@dataclass(frozen=True)
class RepoProfile:
    name: str
    path: Path
    argocd: Path
    kind: str
    prefix: dict[str, str]
    values: dict[str, list[str]]
    profile: dict[str, str]
    helpers: tuple[str, ...]
    migration_globs: tuple[str, ...]
    always_required: tuple[str, ...]
    shell_files: tuple[str, ...]
    dynamic: dict[str, tuple[str, ...]]


@dataclass
class ScanResult:
    names: dict[str, CodeName]
    migration_only: dict[str, CodeName]
    unresolved: list[Unresolved]
    warnings: list[str]


class _Names:
    """Accumulates the reads of one name across files, then freezes them into `CodeName`s."""

    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def add(self, name: str, required: bool, kind: str, where: str) -> None:
        item = self._items.setdefault(
            name, {"required": False, "kind": kind, "where": [], "count": 0}
        )
        item["required"] = item["required"] or required
        if KIND_ORDER[kind] < KIND_ORDER[item["kind"]]:
            item["kind"] = kind
        item["count"] += 1
        if where not in item["where"] and len(item["where"]) < MAX_WHERE:
            item["where"].append(where)

    def names(self) -> set[str]:
        return set(self._items)

    def force_required(self, names: tuple[str, ...]) -> None:
        for name in names:
            if name.upper() in self._items:
                self._items[name.upper()]["required"] = True

    def build(self) -> dict[str, CodeName]:
        return {
            name: CodeName(name, i["required"], i["kind"], tuple(i["where"]), i["count"])
            for name, i in sorted(self._items.items())
        }


def _is_test_path(path: str) -> bool:
    return "tests" in path.split("/")[:-1]


@dataclass
class _Field:
    name: str
    line: int
    required: bool
    alias: str | None
    annotation_names: frozenset[str]


@dataclass
class _Class:
    name: str
    path: str
    bases: tuple[str, ...]
    prefix: str | None
    fields: list[_Field]


def _base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _call_name(node: ast.expr) -> str | None:
    return _base_name(node.func) if isinstance(node, ast.Call) else None


def _string(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _keyword(call: ast.Call, key: str) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == key:
            return keyword.value
    return None


def _annotation_names(annotation: ast.expr) -> frozenset[str]:
    found: set[str] = set()
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.update(re.findall(r"[A-Za-z_]\w*", node.value))
    return frozenset(found)


def _is_class_var(annotation: ast.expr) -> bool:
    target = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    return _base_name(target) == "ClassVar"


def _field_call(annotation: ast.expr, value: ast.expr | None) -> ast.Call | None:
    """The `Field(...)` call of a field: its default value, or inside `Annotated[..., Field()]`."""
    if _call_name(value) == "Field":
        return value  # type: ignore[return-value]
    if isinstance(annotation, ast.Subscript) and _base_name(annotation.value) == "Annotated":
        elements = annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else []
        for element in elements[1:]:
            if _call_name(element) == "Field":
                return element  # type: ignore[return-value]
    return None


def _alias(call: ast.Call) -> str | None:
    for key in ALIAS_KEYS:
        node = _keyword(call, key)
        if node is None:
            continue
        if _call_name(node) == "AliasChoices" and isinstance(node, ast.Call) and node.args:
            return _string(node.args[0])
        return _string(node)
    return None


def _has_default(call: ast.Call | None, value: ast.expr | None) -> bool:
    if value is not None and value is not call:
        return not _is_ellipsis(value)
    if call is None:
        return False
    if call.args:
        return not _is_ellipsis(call.args[0])
    return _keyword(call, "default") is not None or _keyword(call, "default_factory") is not None


def _is_ellipsis(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is Ellipsis


def _class_fields(node: ast.ClassDef) -> list[_Field]:
    fields = []
    for statement in node.body:
        if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
            continue
        name = statement.target.id
        if name.startswith("_") or name == "model_config" or _is_class_var(statement.annotation):
            continue
        call = _field_call(statement.annotation, statement.value)
        fields.append(
            _Field(
                name=name,
                line=statement.lineno,
                required=not _has_default(call, statement.value),
                alias=_alias(call) if call is not None else None,
                annotation_names=_annotation_names(statement.annotation),
            )
        )
    return fields


def _config_prefix(node: ast.ClassDef, path: str, warnings: list[str]) -> str | None:
    """The `env_prefix` of the class's own config, `None` when it sets none."""
    for statement in node.body:
        prefix_node = None
        if isinstance(statement, ast.Assign | ast.AnnAssign):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            if any(isinstance(t, ast.Name) and t.id == "model_config" for t in targets):
                prefix_node = _prefix_node(statement.value)
        elif isinstance(statement, ast.ClassDef) and statement.name == "Config":
            prefix_node = _old_style_prefix_node(statement)
        if prefix_node is not None:
            return _literal_prefix(prefix_node, path, warnings)
    return None


def _old_style_prefix_node(config: ast.ClassDef) -> ast.expr | None:
    for statement in config.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == SETTINGS_CONFIG_KEY for t in statement.targets
        ):
            return statement.value
    return None


def _prefix_node(value: ast.expr | None) -> ast.expr | None:
    if isinstance(value, ast.Call):
        return _keyword(value, SETTINGS_CONFIG_KEY)
    if isinstance(value, ast.Dict):
        for key, item in zip(value.keys, value.values, strict=True):
            if _string(key) == SETTINGS_CONFIG_KEY:
                return item
    return None


def _literal_prefix(node: ast.expr, path: str, warnings: list[str]) -> str:
    prefix = _string(node)
    if prefix is None:
        warnings.append(
            f"{path}:{node.lineno}: env_prefix is not a string literal; its names are read "
            "without a prefix"
        )
        return ""
    return prefix


def _parse(path: str, content: bytes, warnings: list[str]) -> ast.Module | None:
    try:
        return ast.parse(content, filename=path)
    except SyntaxError as error:
        warnings.append(f"{path}:{error.lineno or 1}: syntax error, file skipped")
    except ValueError:
        warnings.append(f"{path}:1: not readable as Python, file skipped")
    return None


def _python_files(files: dict[str, bytes]) -> list[str]:
    return sorted(p for p in files if p.endswith(".py") and not _is_test_path(p))


def _collect_classes(trees: dict[str, ast.Module], warnings: list[str]) -> dict[str, list[_Class]]:
    classes: dict[str, list[_Class]] = {}
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = tuple(b for b in map(_base_name, node.bases) if b)
                classes.setdefault(node.name, []).append(
                    _Class(
                        name=node.name,
                        path=path,
                        bases=bases,
                        prefix=_config_prefix(node, path, warnings),
                        fields=_class_fields(node),
                    )
                )
    return classes


class _Hierarchy:
    """Which classes reach `BaseSettings`, and the prefix and fields each one inherits."""

    def __init__(self, classes: dict[str, list[_Class]]) -> None:
        self.classes = classes
        self._settings: dict[int, bool] = {}

    def is_settings_name(self, name: str) -> bool:
        return name == SETTINGS_BASE or any(self.is_settings(c) for c in self.classes.get(name, ()))

    def is_settings(self, info: _Class, seen: frozenset[int] = frozenset()) -> bool:
        key = id(info)
        if key in seen:
            return False
        if key not in self._settings:
            self._settings[key] = any(
                base == SETTINGS_BASE
                or any(self.is_settings(c, seen | {key}) for c in self.classes.get(base, ()))
                for base in info.bases
            )
        return self._settings[key]

    def _settings_bases(self, info: _Class) -> list[_Class]:
        found = []
        for base in info.bases:
            candidates = [c for c in self.classes.get(base, ()) if c is not info]
            found.extend(c for c in candidates[:1] if self.is_settings(c))
        return found

    def prefix(self, info: _Class, seen: frozenset[int] = frozenset()) -> str:
        if info.prefix is not None:
            return info.prefix
        for base in self._settings_bases(info):
            if id(base) not in seen:
                return self.prefix(base, seen | {id(info)})
        return ""

    def fields(self, info: _Class, seen: frozenset[int] = frozenset()) -> list[tuple[_Field, str]]:
        """The fields of the class, inherited first, with the path of the declaring class."""
        merged: dict[str, tuple[_Field, str]] = {}
        for base in self._settings_bases(info):
            if id(base) not in seen:
                for field, path in self.fields(base, seen | {id(info)}):
                    merged[field.name] = (field, path)
        for field in info.fields:
            merged[field.name] = (field, info.path)
        return list(merged.values())


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """`*` stays inside a folder, `**` crosses folders, `**/` also matches no folder at all."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


class _Sinks:
    """Where the reads of a file go: the regular names, or the migration-only ones."""

    def __init__(self, profile: RepoProfile) -> None:
        self.regular = _Names()
        self.migration = _Names()
        self.unresolved: list[Unresolved] = []
        self._migration = [_glob_regex(g) for g in profile.migration_globs]

    def for_path(self, path: str) -> tuple[_Names, str]:
        if any(m.match(path) for m in self._migration):
            return self.migration, "migration"
        return self.regular, ""


class _ReadVisitor(ast.NodeVisitor):
    """The direct reads of one file: `os.getenv`, `os.environ` and the configured helpers."""

    def __init__(self, path: str, helpers: tuple[str, ...], sinks: _Sinks) -> None:
        self._path = path
        self._helpers = helpers
        self._names, self._migration_kind = sinks.for_path(path)
        self._unresolved = sinks.unresolved
        self._functions: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._functions.append(node.name)
        self.generic_visit(node)
        self._functions.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        kind = self._call_kind(node.func)
        if kind is not None:
            label, is_helper = kind
            key = node.args[0] if node.args else _keyword(node, "name") or _keyword(node, "key")
            if key is not None:
                required = is_helper and len(node.args) == 1 and _keyword(node, "default") is None
                self._read(key, label, required, node.lineno)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if isinstance(node.ctx, ast.Load) and _is_environ(node.value):
            self._read(node.slice, "os.environ", True, node.lineno)
        self.generic_visit(node)

    def _call_kind(self, func: ast.expr) -> tuple[str, bool] | None:
        name = _base_name(func)
        if name in self._helpers:
            return name, True
        if isinstance(func, ast.Name) and func.id == "getenv":
            return "getenv", False
        if isinstance(func, ast.Attribute):
            if func.attr == "getenv" and _base_name(func.value) == "os":
                return "os.getenv", False
            if func.attr == "get" and _is_environ(func.value):
                return "os.environ.get", False
        return None

    def _read(self, key: ast.expr, label: str, required: bool, line: int) -> None:
        where = f"{self._path}:{line}"
        literal = _string(key)
        if literal is not None:
            self._names.add(literal.upper(), required, self._migration_kind or "helper", where)
        elif not any(f in self._helpers for f in self._functions):
            self._unresolved.append(Unresolved(where, label))


def _is_environ(node: ast.expr) -> bool:
    return _base_name(node) == "environ"


def scan_python(files: dict[str, bytes], profile: RepoProfile) -> ScanResult:
    warnings: list[str] = []
    trees = {}
    for path in _python_files(files):
        tree = _parse(path, files[path], warnings)
        if tree is not None:
            trees[path] = tree
    sinks = _Sinks(profile)
    hierarchy = _Hierarchy(_collect_classes(trees, warnings))
    for infos in hierarchy.classes.values():
        for info in infos:
            if hierarchy.is_settings(info):
                _add_settings(sinks, hierarchy, info, profile)
    for path, tree in trees.items():
        _ReadVisitor(path, profile.helpers, sinks).visit(tree)
    sinks.regular.force_required(profile.always_required)
    migration = {n: i for n, i in sinks.migration.build().items() if n not in sinks.regular.names()}
    sinks.unresolved.sort(key=lambda u: (_path_of(u.where), _line_of(u.where)))
    return ScanResult(sinks.regular.build(), migration, sinks.unresolved, warnings)


def _path_of(where: str) -> str:
    return where.rsplit(":", 1)[0]


def _line_of(where: str) -> int:
    return int(where.rsplit(":", 1)[1])


def _add_settings(sinks: _Sinks, hierarchy: _Hierarchy, info: _Class, profile: RepoProfile) -> None:
    dynamic = profile.dynamic.get(info.name)
    prefixes = dynamic if dynamic is not None else (hierarchy.prefix(info),)
    for field, path in hierarchy.fields(info):
        if any(hierarchy.is_settings_name(n) for n in field.annotation_names):
            continue
        target, migration_kind = sinks.for_path(path)
        kind = migration_kind or ("settings" if dynamic is None else "dynamic")
        for prefix in prefixes:
            name = (field.alias or prefix + field.name).upper()
            target.add(name, field.required, kind, f"{path}:{field.line}")


SHELL_EXPANSION = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:?[-=+])?")
SHELL_ASSIGNMENT = re.compile(
    r"^\s*(?:(?:export|local|readonly)\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$"
)
SHELL_LOOP_VARIABLE = re.compile(r"^\s*for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b")
SHELL_READ = re.compile(r"\bread\s+((?:-\w+\s+)*)([A-Za-z_][A-Za-z0-9_ ]*)")


def _shell_assigned(lines: list[str]) -> set[str]:
    """Names the script sets itself, unless the value is read from the same name's environment."""
    assigned: set[str] = set()
    for line in lines:
        match = SHELL_ASSIGNMENT.match(line)
        if match and not re.search(rf"\$\{{?{match.group(1)}\b", match.group(2)):
            assigned.add(match.group(1))
        loop = SHELL_LOOP_VARIABLE.match(line)
        if loop:
            assigned.add(loop.group(1))
        read = SHELL_READ.search(line)
        if read:
            assigned.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", read.group(2).split(";")[0]))
    return assigned


def scan_shell(files: dict[str, bytes], shell_files: list[str]) -> ScanResult:
    """`${NAME}`, `${NAME-...}`, `${NAME:-...}` in the shell files, minus what the script sets."""
    found = _Names()
    warnings = []
    for path in shell_files:
        if path not in files:
            warnings.append(f"{path}: shell file not found at that commit")
            continue
        lines = files[path].decode("utf-8", errors="replace").splitlines()
        assigned = _shell_assigned(lines)
        for number, line in enumerate(lines, start=1):
            if line.lstrip().startswith("#"):
                continue
            for match in SHELL_EXPANSION.finditer(line):
                name = match.group(1)
                if name not in assigned:
                    found.add(name.upper(), match.group(2) is None, "shell", f"{path}:{number}")
    return ScanResult(found.build(), {}, [], warnings)


def _git(repo: Path, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(repo), *args], input=stdin, capture_output=True)


def resolve_commit(repo: Path, ref: str) -> str:
    """The full sha of `ref` in the local clone; never fetches."""
    if not repo.is_dir():
        raise SetupError(f"{repo} is not a directory")
    result = _git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
    if result.returncode != 0:
        raise SetupError(f"commit {ref} not found in {repo}: git fetch first (ws never fetches)")
    return result.stdout.decode().strip()


def files_at(repo: Path, ref: str, only: Callable[[str], bool] | None = None) -> dict[str, bytes]:
    """The regular files of `repo` at `ref`, read from the git objects, never the working tree.

    `only` limits which paths are read (a front repo has many files no scanner needs).
    """
    sha = resolve_commit(repo, ref)
    listing = _git(repo, "ls-tree", "-r", "-z", sha)
    if listing.returncode != 0:
        raise SetupError(f"git ls-tree failed for {ref} in {repo}")
    wanted: dict[str, str] = {}
    for entry in listing.stdout.split(b"\0"):
        if not entry:
            continue
        meta, _, raw_path = entry.partition(b"\t")
        mode, kind, blob = meta.decode().split(" ")
        path = raw_path.decode("utf-8", errors="replace")
        if kind == "blob" and mode in REGULAR_MODES and (only is None or only(path)):
            wanted[path] = blob
    contents = _read_blobs(repo, sorted(set(wanted.values())))
    return {path: contents[blob] for path, blob in wanted.items() if blob in contents}


def _read_blobs(repo: Path, shas: list[str]) -> dict[str, bytes]:
    if not shas:
        return {}
    result = _git(repo, "cat-file", "--batch", stdin=("\n".join(shas) + "\n").encode())
    if result.returncode != 0:
        raise SetupError(f"git cat-file failed in {repo}")
    data, position, contents = result.stdout, 0, {}
    while position < len(data):
        end = data.index(b"\n", position)
        header = data[position:end].split(b" ")
        position = end + 1
        if header[1] == b"missing":
            continue
        size = int(header[2])
        contents[header[0].decode()] = data[position : position + size]
        position += size + 1
    return contents


YamlLine = tuple[int, int, str]  # (line number, indent, content without comment)
IMAGE_TAG = re.compile(r"^[A-Za-z][A-Za-z0-9]*-([0-9a-f]{7,40})$")
CHART_KEY = "standard-service-chart"
ENV_BLOCK = re.compile(r"^(env|extraEnv):\s*(.*)$")
MAP_KEY = re.compile(r"""^(['"]?)([^:'"\s][^:'"]*?)\1\s*:(?:\s|$)""")
FLOW_NAME = re.compile(r"""\bname\s*:\s*['"]?([^,'"}\s]+)""")


def _yaml_lines(text: str) -> list[YamlLine]:
    lines = []
    for number, raw in enumerate(text.splitlines(), start=1):
        content = re.sub(r"(^|\s)#.*$", "", raw).rstrip()
        if content.strip():
            lines.append((number, len(content) - len(content.lstrip()), content.strip()))
    return lines


def _unquote(value: str) -> str:
    value = value.strip()
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"" else value


def deployed_sha(argocd: Path, values: list[str]) -> str:
    """The commit of the image tag (`<env>-<sha>`) in the environment's argocd values."""
    if not values:
        raise SetupError("no values file configured for this environment")
    shas: dict[str, str] = {}
    for name in values:
        path = argocd / name
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            raise SetupError(f"values file {name} not found in {argocd}") from None
        tag = _image_tag(text)
        if tag is None:
            raise SetupError(f"{name}: no image tag under {CHART_KEY}.image")
        match = IMAGE_TAG.match(tag)
        if not match:
            raise SetupError(f"{name}: image tag {tag} is not <env>-<sha>")
        shas[name] = match.group(1)
    if len(set(shas.values())) > 1:
        raise SetupError("the image tags of the values files differ: " + ", ".join(sorted(shas)))
    return next(iter(shas.values()))


def _image_tag(text: str) -> str | None:
    stack: list[tuple[int, str]] = []
    for _, indent, content in _yaml_lines(text):
        while stack and stack[-1][0] >= indent:
            stack.pop()
        key, _, value = content.partition(":")
        if not value.strip():
            stack.append((indent, key.strip()))
        elif key == "tag" and [k for _, k in stack][-2:] == [CHART_KEY, "image"]:
            return _unquote(value)
    return None


def argocd_env_names(path: str, text: str) -> tuple[set[str], list[str]]:
    """Names in the `env` and `extraEnv` blocks of one values file, and what could not be read."""
    lines = _yaml_lines(text)
    names: set[str] = set()
    warnings: list[str] = []
    index = 0
    while index < len(lines):
        number, indent, content = lines[index]
        index += 1
        match = ENV_BLOCK.match(content)
        if not match:
            continue
        key, inline = match.groups()
        if inline:
            if inline not in ("[]", "{}", "null", "~"):
                warnings.append(f"{path}:{number}: cannot read the inline {key} value; skipped")
            continue
        block = []
        is_list = index < len(lines) and _is_item(lines[index])
        while index < len(lines) and _in_block(lines[index], indent, is_list):
            block.append(lines[index])
            index += 1
        if block:
            reader = _list_names if _is_item(block[0]) else _map_names
            reader(path, key, block, names, warnings)
    return names, warnings


def _is_item(line: YamlLine) -> bool:
    return line[2] == "-" or line[2].startswith("- ")


def _in_block(line: YamlLine, base: int, is_list: bool) -> bool:
    return line[1] > base or (line[1] == base and is_list and _is_item(line))


def _list_names(
    path: str, key: str, block: list[YamlLine], names: set[str], warnings: list[str]
) -> None:
    item_indent = block[0][1]
    item_line, key_column, name = 0, 0, None

    def close() -> None:
        if item_line and name is None:
            warnings.append(f"{path}:{item_line}: {key} item without a readable name; skipped")
        elif name is not None:
            names.add(name.upper())

    for number, indent, content in block:
        if indent == item_indent and _is_item((number, indent, content)):
            close()
            rest = content[1:].lstrip()
            item_line, key_column, name = number, indent + len(content) - len(rest), None
        else:
            rest = content if indent == key_column else ""
        found = FLOW_NAME.search(rest) if rest.startswith("{") else None
        if found:
            name = found.group(1)
        elif rest.startswith("name:"):
            name = _unquote(rest[len("name:") :]) or None
    close()


def _map_names(
    path: str, key: str, block: list[YamlLine], names: set[str], warnings: list[str]
) -> None:
    base = block[0][1]
    for number, indent, content in block:
        if indent != base:
            continue
        match = MAP_KEY.match(content)
        if match:
            names.add(match.group(2).upper())
        else:
            warnings.append(f"{path}:{number}: {key} entry is not a NAME: value pair; skipped")
