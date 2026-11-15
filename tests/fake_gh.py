"""A fake `gh` for the release tests: no network, no GitHub.

`fake_gh` puts a Python script named `gh` first on `PATH` and returns a `FakeGh` to arrange and
inspect it. The script keeps all its state in one JSON file (`FakeGh.state_path`): the PRs per
slug, the failures and hangs to simulate, the log of every call and the body text of each create
or edit. Arrange with `add_pr`, `set_checks`, `fail`, `hang`, `logged_out`; inspect with `calls`,
`writes`, `prs`, `bodies`.

Supported: `auth status`, `pr list`, `pr view`, `pr create`, `pr edit N` (`--body-file`,
`--title`, `--base`, `--add-label`), `pr close N --comment`, `pr comment N --body`. Strict: unknown
flags, unknown `--json` fields, a bad `--state` and a
`pr create` without `--title` or a body exit 1.
Any other verb exits 1 with `unsupported`.
"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

READ_VERBS = (["auth", "status"], ["pr", "list"], ["pr", "view"])

SCRIPT = r"""#!{python}
import json, sys, time

STATE = {state!r}
argv = sys.argv[1:]
state = json.load(open(STATE))
verb = " ".join(argv[:2])
state["calls"].append(argv)


def save():
    json.dump(state, open(STATE, "w"))


def option(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def values(name):
    return [argv[i + 1] for i, a in enumerate(argv) if a == name]


def fail(message, code=1):
    save()
    print(message, file=sys.stderr)
    sys.exit(code)


def find(slug, number):
    for item in state["prs"].get(slug, []):
        if item["number"] == number:
            return item
    fail(f"no pull requests found for {{slug}}#{{number}}")


if verb in state["hang"]:
    save()
    time.sleep(30)
for key in (verb, verb + " " + str(option("-R"))):
    if key in state["failures"]:
        stderr, code = state["failures"][key]
        fail(stderr, code)
if verb == "auth status":
    if state["logged_out"]:
        fail("You are not logged into any GitHub hosts. Run gh auth login to authenticate.")
    save()
    sys.exit(0)

slug = option("-R")


JSON_FIELDS = {{
    "number", "state", "baseRefName", "headRefName", "title", "url", "mergedAt", "body",
    "labels", "assignees", "mergeable", "statusCheckRollup",
}}
ALLOWED_FLAGS = {{
    "pr list": {{"-R", "--state", "--head", "--base", "--json", "--limit"}},
    "pr view": {{"-R", "--json"}},
    "pr create": {{
        "-R", "--base", "--head", "--title", "--body", "--body-file", "--label", "--assignee",
    }},
    "pr edit": {{"-R", "--title", "--base", "--body", "--body-file", "--add-label"}},
    "pr close": {{"-R", "--comment"}},
    "pr comment": {{"-R", "--body"}},
}}
if verb in ALLOWED_FLAGS:
    position = 2
    while position < len(argv):
        arg = argv[position]
        if not arg.startswith("-"):
            position += 1
            continue
        if "=" in arg and arg.startswith("--"):
            fail("unsupported form: " + arg)
        if arg not in ALLOWED_FLAGS[verb]:
            fail("unknown flag: " + arg)
        if position + 1 >= len(argv):
            fail("flag needs an argument: " + arg)
        position += 2
if option("--json"):
    for name in option("--json").split(","):
        if name not in JSON_FIELDS:
            fail("Unknown JSON field: " + name)
if option("--state", "all") not in ("open", "closed", "merged", "all"):
    fail("invalid state: " + option("--state"))


def project(item, fields):
    return {{name: item[name] for name in fields.split(",") if name in item}}


if verb in ("pr list", "pr view") and state.get("raw") is not None:
    save()
    print(state["raw"])
    sys.exit(0)
if verb == "pr list":
    found = [
        item for item in state["prs"].get(slug, [])
        if (not option("--head") or item["headRefName"] == option("--head"))
        and (not option("--base") or item["baseRefName"] == option("--base"))
        and (option("--state", "all") == "all" or item["state"].lower() == option("--state"))
    ]
    save()
    print(json.dumps([project(i, option("--json")) for i in found]))
elif verb == "pr view":
    item = find(slug, int(argv[2]))
    save()
    print(json.dumps(project(item, option("--json"))))
elif verb == "pr create":
    if not option("--title"):
        fail("title is required")
    if "--body" not in argv and "--body-file" not in argv:
        fail("body is required: use --body or --body-file")
    prs = state["prs"].setdefault(slug, [])
    number = max([item["number"] for item in prs], default=0) + 1
    url = "https://github.com/" + slug + "/pull/" + str(number)
    prs.append({{
        "number": number, "state": "OPEN", "baseRefName": option("--base"),
        "headRefName": option("--head"), "title": option("--title", ""), "url": url,
        "mergedAt": None, "body": "", "mergeable": "UNKNOWN", "statusCheckRollup": [],
        "labels": [{{"name": n}} for n in values("--label")],
        "assignees": [{{"login": n}} for n in values("--assignee")],
    }})
    if "--body-file" in argv:
        body = open(option("--body-file")).read()
        prs[-1]["body"] = body
        state["bodies"][str(number)] = body
    save()
    print(url)
elif verb == "pr edit":
    item = find(slug, int(argv[2]))
    if option("--title"):
        item["title"] = option("--title")
    if option("--base"):
        item["baseRefName"] = option("--base")
    item["labels"] += [{{"name": n}} for n in values("--add-label")]
    if "--body-file" in argv:
        item["body"] = open(option("--body-file")).read()
        state["bodies"][argv[2]] = item["body"]
    save()
elif verb == "pr close":
    item = find(slug, int(argv[2]))
    item["state"] = "CLOSED"
    save()
elif verb == "pr comment":
    find(slug, int(argv[2]))
    save()
else:
    fail("unsupported: gh " + " ".join(argv))
"""


class FakeGh:
    def __init__(self, state_path: Path):
        self.state_path = state_path
        self._write(
            {
                "prs": {},
                "failures": {},
                "hang": [],
                "logged_out": False,
                "calls": [],
                "bodies": {},
            }
        )

    def _read(self) -> dict:
        return json.loads(self.state_path.read_text())

    def _write(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state))

    def add_pr(
        self,
        slug: str,
        number: int,
        head: str,
        base: str,
        state: str = "OPEN",
        title: str = "t",
        body: str = "b",
        labels=(),
        assignees=(),
        merged_at: str | None = None,
    ) -> None:
        data = self._read()
        data["prs"].setdefault(slug, []).append(
            {
                "number": number,
                "state": state,
                "baseRefName": base,
                "headRefName": head,
                "title": title,
                "url": f"https://github.com/{slug}/pull/{number}",
                "mergedAt": merged_at,
                "body": body,
                "mergeable": "UNKNOWN",
                "statusCheckRollup": [],
                "labels": [{"name": name} for name in labels],
                "assignees": [{"login": name} for name in assignees],
            }
        )
        self._write(data)

    def set_checks(self, slug: str, number: int, mergeable: str, checks: dict[str, str]) -> None:
        """Set what `pr view --json mergeable,statusCheckRollup` answers: name -> conclusion."""
        data = self._read()
        for item in data["prs"][slug]:
            if item["number"] == number:
                item["mergeable"] = mergeable
                item["statusCheckRollup"] = [
                    {"name": name, "conclusion": conclusion} for name, conclusion in checks.items()
                ]
        self._write(data)

    def fail(self, verb: str, stderr: str, code: int = 1, repo: str | None = None) -> None:
        """Make every call of `verb` (such as "pr create") print `stderr` and exit `code`.
        With `repo` (a slug) only the calls of `-R repo` fail."""
        data = self._read()
        data["failures"][verb if repo is None else f"{verb} {repo}"] = [stderr, code]
        self._write(data)

    def clear_failures(self) -> None:
        data = self._read()
        data["failures"] = {}
        self._write(data)

    def hang(self, verb: str) -> None:
        """Make every call of `verb` sleep far past any timeout a test sets."""
        data = self._read()
        data["hang"].append(verb)
        self._write(data)

    def raw_output(self, text: str) -> None:
        """Make `pr list` and `pr view` print `text` verbatim (to test malformed output)."""
        data = self._read()
        data["raw"] = text
        self._write(data)

    def logged_out(self) -> None:
        data = self._read()
        data["logged_out"] = True
        self._write(data)

    @property
    def calls(self) -> list[list[str]]:
        return self._read()["calls"]

    @property
    def writes(self) -> list[list[str]]:
        """Every call that is not `auth status`, `pr list` or `pr view`."""
        return [call for call in self.calls if call[:2] not in READ_VERBS]

    def prs(self, slug: str) -> list[dict]:
        return self._read()["prs"].get(slug, [])

    @property
    def bodies(self) -> dict[int, str]:
        """The body file's text at each `pr create` or `pr edit`, by PR number."""
        return {int(number): text for number, text in self._read()["bodies"].items()}


@pytest.fixture
def fake_gh(tmp_path, monkeypatch) -> FakeGh:
    folder = tmp_path / "fake-gh-bin"
    folder.mkdir()
    fake = FakeGh(tmp_path / "fake-gh-state.json")
    script = folder / "gh"
    script.write_text(SCRIPT.format(python=sys.executable, state=str(fake.state_path)))
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{folder}:{os.environ.get('PATH', '')}")
    return fake
