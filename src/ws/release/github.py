"""The `gh` adapter: reads PRs and writes through the GitHub CLI, nothing else.

Writes are split by what the caller may do next. `GhFailed` means GitHub refused (a 4xx, a bad
argument): nothing happened, fix and retry. `GhUncertain` means the request may have landed (a
timeout, an HTTP 5xx, a lost connection): look at GitHub before sending again.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass


class GhMissing(Exception):
    """`gh` is not installed or not logged in."""


class GhFailed(Exception):
    """`gh` exited with an error and the write did not happen."""


class GhUncertain(Exception):
    """A write was sent and the outcome is unknown (timeout, HTTP 5xx, connection error)."""


UNCERTAIN_STDERR = re.compile(
    r"HTTP 5\d\d|timed? ?out|connection (reset|refused|error)|could not resolve host"
    r"|dial tcp|EOF|network is unreachable",
    re.IGNORECASE,
)
LIST_FIELDS = "number,state,baseRefName,headRefName,title,url,mergedAt"
VIEW_FIELDS = LIST_FIELDS + ",body,labels,assignees"


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str
    base: str
    head: str
    title: str
    url: str
    merged_at: str | None
    body: str = ""
    labels: tuple[str, ...] = ()
    assignees: tuple[str, ...] = ()


def to_pull_request(raw: dict) -> PullRequest:
    return PullRequest(
        number=raw["number"],
        state=raw["state"],
        base=raw["baseRefName"],
        head=raw["headRefName"],
        title=raw["title"],
        url=raw["url"],
        merged_at=raw.get("mergedAt") or None,
        body=raw.get("body") or "",
        labels=tuple(item["name"] for item in raw.get("labels") or ()),
        assignees=tuple(item["login"] for item in raw.get("assignees") or ()),
    )


class Gh:
    def __init__(self, timeout: float = 60):
        self.timeout = timeout

    def require_auth(self) -> None:
        if shutil.which("gh") is None:
            raise GhMissing("gh is not installed")
        try:
            done = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True, timeout=self.timeout
            )
        except subprocess.TimeoutExpired:
            raise GhMissing("gh is not logged in: run gh auth login") from None
        if done.returncode != 0:
            raise GhMissing("gh is not logged in: run gh auth login")

    def prs(
        self, slug: str, *, head: str | None = None, base: str | None = None, state: str = "all"
    ) -> list[PullRequest]:
        args = ["pr", "list", "-R", slug, "--state", state]
        if head:
            args += ["--head", head]
        if base:
            args += ["--base", base]
        args += ["--json", LIST_FIELDS, "--limit", "100"]
        return [to_pull_request(item) for item in json.loads(self._read(args))]

    def pr(self, slug: str, number: int) -> PullRequest:
        out = self._read(["pr", "view", str(number), "-R", slug, "--json", VIEW_FIELDS])
        return to_pull_request(json.loads(out))

    def checks(self, slug: str, number: int) -> dict:
        out = self._read(
            ["pr", "view", str(number), "-R", slug, "--json", "mergeable,statusCheckRollup"]
        )
        raw = json.loads(out)
        checks: dict[str, str] = {}
        for item in raw.get("statusCheckRollup") or ():
            name = item.get("name") or item.get("context") or ""
            checks[name] = item.get("conclusion") or item.get("state") or item.get("status") or ""
        return {"mergeable": raw.get("mergeable") or "", "checks": checks}

    def write(self, args: tuple[str, ...], body: str | None) -> str:
        """Run a `gh` write and return its stdout. A body goes by a mode-600 file, removed after."""
        argv = list(args)
        path = None
        if body is not None:
            handle, path = tempfile.mkstemp(prefix="ws-release-", suffix=".md")
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(body)
            argv += ["--body-file", path]
        try:
            try:
                done = subprocess.run(
                    ["gh", *argv], capture_output=True, text=True, timeout=self.timeout
                )
            except subprocess.TimeoutExpired:
                raise GhUncertain(f"gh {' '.join(args[:2])} timed out") from None
            except OSError as error:
                raise GhFailed(f"gh could not run: {error}") from None
        finally:
            if path is not None:
                os.unlink(path)
        if done.returncode != 0:
            message = done.stderr.strip() or f"gh exited {done.returncode}"
            if UNCERTAIN_STDERR.search(message):
                raise GhUncertain(message)
            raise GhFailed(message)
        return done.stdout.strip()

    def _read(self, args: list[str]) -> str:
        try:
            done = subprocess.run(
                ["gh", *args], capture_output=True, text=True, timeout=self.timeout
            )
        except subprocess.TimeoutExpired:
            raise GhFailed(f"gh {' '.join(args[:2])} timed out") from None
        except OSError as error:
            raise GhFailed(f"gh could not run: {error}") from None
        if done.returncode != 0:
            raise GhFailed(done.stderr.strip() or f"gh exited {done.returncode}")
        return done.stdout
