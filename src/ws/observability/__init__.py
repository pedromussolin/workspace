"""Neutral observability layer: the provider is chosen by `[observability] provider`.

A provider is a module `<name>_adapter` of this package; it is found by file name.
"""

import importlib
import pkgutil

from ws.observability.port import Observability, Setup
from ws.userconfig import ConfigMissing, load_table

SUFFIX = "_adapter"


def providers() -> tuple[str, ...]:
    names = (found.name for found in pkgutil.iter_modules(__path__))
    return tuple(sorted(name.removesuffix(SUFFIX) for name in names if name.endswith(SUFFIX)))


def open_observability() -> Observability:
    known = ", ".join(providers())
    try:
        table = load_table("observability")
    except ConfigMissing:
        table = {}
    provider = table.get("provider")
    if not provider:
        raise Setup(f"[observability] provider is not set in config.toml; known: {known}")
    if provider not in providers():
        raise Setup(f"[observability] provider {provider!r} is unknown; known: {known}")
    module = importlib.import_module(f"ws.observability.{provider}{SUFFIX}")
    return module.from_config(table)
