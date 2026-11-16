"""The contributor and agent docs hang together: entry points, links, tags and records."""

import re
from pathlib import Path

import pytest

from ws import bootstrap

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CONVENTIONS = DOCS / "conventions"
HOW_TO = DOCS / "how-to"
ADR = DOCS / "adr"
BUILDING_SKILLS = ROOT / ".claude" / "skills"

LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
TAG = re.compile(r"\[(test: [^\]]+|hook|gate|script|review)\]$")
TEST_FILE = re.compile(r"tests/[\w./-]+\.py")
ADR_FILE = re.compile(r"\d{4}-[a-z0-9-]+\.md")
STATUS = re.compile(r"(accepted|proposed|rejected|deprecated|superseded by \d{4})")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
ADR_SECTIONS = ("Context and Problem Statement", "Decision Outcome", "Consequences")


def links_of(path: Path) -> set[Path]:
    """Local Markdown link targets of a file, resolved against its folder."""
    text = path.read_text(encoding="utf-8")
    return {
        (path.parent / target).resolve() for target in LINK.findall(text) if "://" not in target
    }


def rule_items(text: str) -> list[str]:
    """Each top-level list item (a line starting with "- "), with its indented continuation."""
    items: list[list[str]] = []
    current: list[str] | None = None
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            current = None
            continue
        if fenced:
            continue
        if line.startswith("- "):
            current = [line]
            items.append(current)
        elif current is not None and (not line.strip() or line[0].isspace()):
            current.append(line)
        else:
            current = None
    return [" ".join(" ".join(item).split()) for item in items]


def front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} has no front matter"
    block = text.split("\n---\n", 1)[0].removeprefix("---\n")
    fields = {}
    for line in block.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def adr_files() -> list[Path]:
    return sorted(path for path in ADR.glob("*.md") if ADR_FILE.fullmatch(path.name))


def test_claude_md_starts_with_the_agents_import():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert text.splitlines()[0] == "@AGENTS.md"


def test_every_doc_is_linked_from_agents_md_or_the_decision_index():
    linked = links_of(ROOT / "AGENTS.md") | links_of(ADR / "README.md")
    docs = [path for folder in (CONVENTIONS, HOW_TO, ADR) for path in folder.glob("*.md")]

    assert len(docs) > 10
    missing = [str(path.relative_to(ROOT)) for path in docs if path.resolve() not in linked]
    assert not missing, f"not linked from AGENTS.md or docs/adr/README.md: {missing}"


def test_every_building_skill_points_to_its_guide():
    skills = sorted(path.parent.name for path in BUILDING_SKILLS.glob("*/SKILL.md"))
    guides = sorted(path.stem for path in HOW_TO.glob("*.md"))

    assert skills == guides
    for name in skills:
        text = (BUILDING_SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        assert f"docs/how-to/{name}.md" in text, f"{name} does not point to its guide"
        assert front_matter(BUILDING_SKILLS / name / "SKILL.md")["name"] == name


def test_the_rule_scan_reads_wrapped_and_nested_items():
    sample = (
        "# Title\n\nIntro.\n\n"
        "- One line. [review]\n"
        "- Wrapped over\n  two lines. [test: tests/a.py; tests/b.py]\n"
        "- Nested:\n  - first;\n  - last. [gate]\n"
        "- Steps:\n  1. one;\n\n  After the list. [hook]\n"
        "- No tag at all.\n\n"
        "A paragraph that ends the list.\n"
    )
    items = rule_items(sample)

    assert [bool(TAG.search(item)) for item in items] == [True, True, True, True, False]
    assert items[1].endswith("two lines. [test: tests/a.py; tests/b.py]")


@pytest.mark.parametrize("path", sorted(CONVENTIONS.glob("*.md")), ids=lambda path: path.name)
def test_every_rule_ends_with_an_enforcement_tag(path):
    items = rule_items(path.read_text(encoding="utf-8"))

    assert items, f"{path.name} has no rules"
    untagged = [item for item in items if not TAG.search(item)]
    assert not untagged, f"rules without a tag: {untagged}"
    for item in items:
        tag = TAG.search(item).group(1)
        if tag.startswith("test: "):
            for name in tag.removeprefix("test: ").split(";"):
                name = name.strip()
                assert TEST_FILE.fullmatch(name), f"bad test path {name!r} in {path.name}"
                assert (ROOT / name).is_file(), f"{name} named in {path.name} does not exist"


@pytest.mark.parametrize("path", adr_files(), ids=lambda path: path.name)
def test_every_decision_record_has_status_date_and_sections(path):
    fields = front_matter(path)
    text = path.read_text(encoding="utf-8")
    headings = {line[3:].strip() for line in text.splitlines() if line.startswith("## ")}

    assert STATUS.fullmatch(fields.get("status", "")), f"{path.name}: status"
    assert DATE.fullmatch(fields.get("date", "")), f"{path.name}: date"
    missing = [section for section in ADR_SECTIONS if section not in headings]
    assert not missing, f"{path.name} lacks {missing}"


def test_decision_records_are_numbered_in_order_from_0001():
    numbers = [int(path.name[:4]) for path in adr_files()]

    assert numbers == list(range(1, len(numbers) + 1))
    assert numbers


def test_setup_links_only_the_daily_use_skills(tmp_path):
    repo = tmp_path / "repo"
    (repo / "skills" / "daily-use").mkdir(parents=True)
    (repo / ".claude" / "skills" / "building").mkdir(parents=True)
    target = tmp_path / "claude-skills"
    setup = bootstrap._Setup(apply=True, by_hand=False)

    bootstrap._link_skills(setup, repo, target)

    assert sorted(path.name for path in target.iterdir()) == ["daily-use"]
