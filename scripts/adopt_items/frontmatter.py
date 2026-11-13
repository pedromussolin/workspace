"""TOML front matter of task items, written without touching the body."""

FENCE = "+++"
ORDER = ("card", "type", "epic", "assignee", "reporter", "blocks", "blocked_by", "relates", "docs")


def _fence_end(text: str) -> int | None:
    """Offset just after the closing fence line, or None when there is no block."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != FENCE:
        return None
    offset = len(lines[0])
    for line in lines[1:]:
        offset += len(line)
        if line.rstrip("\r\n") == FENCE:
            return offset
    return None


def has_front_matter(text: str) -> bool:
    return _fence_end(text) is not None


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{escaped}"'


def dump_fields(fields: dict) -> str:
    lines = []
    for key in ORDER:
        value = fields.get(key)
        if isinstance(value, list):
            if value:
                lines.append(f"{key} = [{', '.join(_quote(v) for v in value)}]")
        elif value:
            lines.append(f"{key} = {_quote(value)}")
    if fields.get("tracker") is False:
        lines.append("tracker = false")
        if fields.get("status"):
            lines.append(f"status = {_quote(fields['status'])}")
    return "".join(f"{line}\n" for line in lines)


def _block(fields: dict) -> str:
    return f"{FENCE}\n{dump_fields(fields)}{FENCE}\n"


def insert_front_matter(text: str, fields: dict) -> str:
    if has_front_matter(text):
        raise ValueError("file already has front matter")
    return _block(fields) + text


def replace_front_matter(text: str, fields: dict) -> str:
    end = _fence_end(text)
    if end is None:
        raise ValueError("file has no front matter")
    return _block(fields) + text[end:]


def _fill(text: str, heading: str, content: str) -> str:
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.rstrip("\r\n") == heading:
            nl = line[len(line.rstrip("\r\n")) :] or "\n"
            rest = lines[i + 1 :]
            insert = [nl, content + nl]
            if rest and rest[0].strip():
                insert.append(nl)
            return "".join(lines[: i + 1] + insert + rest)
    nl = "\r\n" if "\r\n" in text else "\n"
    if text and not text.endswith("\n"):
        text += nl
    sep = nl if text else ""
    return f"{text}{sep}{heading}{nl}{nl}{content}{nl}"


def fill_sections(text: str, scope: str | None, done_when: str | None) -> str:
    if scope:
        text = _fill(text, "## Contexto", scope)
    if done_when:
        text = _fill(text, "## Pronto quando", done_when)
    return text
