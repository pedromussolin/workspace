"""Which env var names a repo reads, against the Parameter Store and argocd (`ws env check`).

Names only. A value from the store never gets here: the sources keep the text before the first
`=` of a line and drop the rest at once, and no message built here quotes a command's output.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

MAX_WHERE = 3
KIND_ORDER = {"settings": 0, "dynamic": 1, "helper": 2, "shell": 3, "migration": 4}
SETTINGS_BASE = "BaseSettings"
SETTINGS_CONFIG_KEY = "env_prefix"
ALIAS_KEYS = ("validation_alias", "alias")


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


def scan_python(files: dict[str, bytes], profile: RepoProfile) -> ScanResult:
    warnings: list[str] = []
    trees = {}
    for path in _python_files(files):
        tree = _parse(path, files[path], warnings)
        if tree is not None:
            trees[path] = tree
    hierarchy = _Hierarchy(_collect_classes(trees, warnings))
    found = _Names()
    for infos in hierarchy.classes.values():
        for info in infos:
            if hierarchy.is_settings(info):
                _add_settings(found, hierarchy, info, profile)
    found.force_required(profile.always_required)
    return ScanResult(found.build(), {}, [], warnings)


def _add_settings(found: _Names, hierarchy: _Hierarchy, info: _Class, profile: RepoProfile) -> None:
    dynamic = profile.dynamic.get(info.name)
    prefixes = dynamic if dynamic is not None else (hierarchy.prefix(info),)
    for field, path in hierarchy.fields(info):
        if any(hierarchy.is_settings_name(n) for n in field.annotation_names):
            continue
        for prefix in prefixes:
            name = (field.alias or prefix + field.name).upper()
            found.add(
                name,
                field.required,
                "settings" if dynamic is None else "dynamic",
                f"{path}:{field.line}",
            )
