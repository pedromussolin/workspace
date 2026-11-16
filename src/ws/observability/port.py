"""The observability port: neutral count checks over traces, logs or metrics.

A document is an `observability-request`; the adapter turns it into a program for its tool, or
into classic-tool calls used as a fallback.
"""

from typing import Protocol, runtime_checkable


class Setup(Exception):
    """The observability tool is not configured (exit 2)."""


@runtime_checkable
class Observability(Protocol):
    kind: str
    tool: str

    def request(self, document: dict) -> str: ...

    def fallback(self, document: dict) -> list[dict]: ...
