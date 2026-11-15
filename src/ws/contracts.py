"""Versioned JSON contracts and a minimal validator for the JSON Schema subset they use."""

import copy
import json
import re
from functools import cache
from importlib import resources

NAME = re.compile(r"[a-z][a-z0-9-]*")
ANNOTATIONS = {"$schema", "$id", "title", "description"}
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
KEYWORDS = ANNOTATIONS | {
    "type",
    "required",
    "properties",
    "additionalProperties",
    "enum",
    "const",
    "items",
}


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def _is_type(value: object, name: str) -> bool:
    actual = _type_name(value)
    if name == "number":
        return actual in ("integer", "number")
    return actual == name


def _same(left: object, right: object) -> bool:
    # Compared as JSON text, so `const: 1` refuses 1.0 and True.
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def _verify(schema: dict, name: str) -> None:
    for keyword in schema:
        if keyword not in KEYWORDS:
            raise ValueError(f"{name}: unsupported keyword {keyword}")
    if "additionalProperties" in schema and schema["additionalProperties"] is not False:
        raise ValueError(f"{name}: additionalProperties must be false")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        for kind in types:
            if kind not in TYPES:
                raise ValueError(f"{name}: unknown type {kind}")
    if "required" in schema:
        required = schema["required"]
        if not isinstance(required, list) or not all(isinstance(k, str) for k in required):
            raise ValueError(f"{name}: required must be a list of strings")
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise ValueError(f"{name}: enum must be a list")
    for sub in schema.get("properties", {}).values():
        _verify(sub, name)
    if isinstance(schema.get("items"), dict):
        _verify(schema["items"], name)


@cache
def _load(name: str) -> dict:
    if not NAME.fullmatch(name):
        raise ValueError(f"unknown contract {name}")
    path = resources.files("ws") / "data" / "contracts" / f"{name}.schema.json"
    if not path.is_file():
        raise ValueError(f"unknown contract {name}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    _verify(schema, name)
    return schema


def load_schema(name: str) -> dict:
    """Return a private copy of the schema, so callers may not corrupt the cached one."""
    return copy.deepcopy(_load(name))


def check(document: object, schema: dict, path: str = "$") -> list[str]:
    if path == "$":
        _verify(schema, "schema")
    for keyword in schema:
        if keyword not in KEYWORDS:
            raise ValueError(f"{path}: unsupported keyword {keyword}")
    problems: list[str] = []
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(document, t) for t in types):
            problems.append(f"{path}: expected {' or '.join(types)}, got {_type_name(document)}")
            return problems
    if "const" in schema and not _same(document, schema["const"]):
        problems.append(f"{path}: expected {json.dumps(schema['const'])}")
    if "enum" in schema and not any(_same(document, option) for option in schema["enum"]):
        options = [o if isinstance(o, str) else json.dumps(o) for o in schema["enum"]]
        problems.append(f"{path}: expected one of {', '.join(options)}")
    if isinstance(document, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in document:
                problems.append(f"{path}: missing required key {key}")
        for key, value in document.items():
            if key in properties:
                problems.extend(check(value, properties[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                problems.append(f"{path}.{key}: unexpected key")
    if isinstance(document, list) and "items" in schema:
        for index, item in enumerate(document):
            problems.extend(check(item, schema["items"], f"{path}[{index}]"))
    return problems


def validate(document: object, schema_name: str) -> list[str]:
    return check(document, load_schema(schema_name))
