"""Neutral observability layer: the provider is chosen by `[observability] provider`."""

import importlib

from ws.observability.port import Observability, Setup
from ws.userconfig import ConfigMissing, load_table

PROVIDERS = {"datadog": "ws.observability.datadog_adapter"}


def providers() -> tuple[str, ...]:
    return tuple(PROVIDERS)


def open_observability() -> Observability:
    known = ", ".join(providers())
    try:
        table = load_table("observability")
    except ConfigMissing:
        table = {}
    provider = table.get("provider")
    if not provider:
        raise Setup(f"[observability] provider is not set in config.toml; known: {known}")
    if provider not in PROVIDERS:
        raise Setup(f"[observability] provider {provider!r} is unknown; known: {known}")
    module = importlib.import_module(PROVIDERS[provider])
    return module.from_config(table)
