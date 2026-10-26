"""Starts a planning project: copies templates/project into projetos/<slug>."""

import re
import shutil
from datetime import date
from pathlib import Path

SLUG_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def new_project(slug: str, root: Path, today: date) -> Path:
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError(
            f"invalid slug {slug!r}: use lowercase letters and digits separated by single hyphens"
        )
    target = root / "projetos" / slug
    if target.exists():
        raise FileExistsError(f"project already exists: {target}")

    shutil.copytree(root / "templates" / "project", target)
    values = {"{{slug}}": slug, "{{data}}": today.strftime("%d/%m/%Y")}
    for markdown in target.rglob("*.md"):
        text = markdown.read_text(encoding="utf-8")
        for placeholder, value in values.items():
            text = text.replace(placeholder, value)
        markdown.write_text(text, encoding="utf-8")
    return target
