"""Markdown → documento do Jira (ADF); recusa o que não sabe converter, citando a linha."""

import re
from dataclasses import dataclass, field

CHECKED = "☑"
UNCHECKED = "☐"

_HEADING = re.compile(r"^(#+)(?:\s+(.*))?$")
_MARKER = re.compile(r"^(\s*)([-*]|\d+\.)(?:\s+(.*))?$")
_RULE = re.compile(r"^\s*(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$")
_CHECKBOX = re.compile(r"^\[([ xX])\](?:\s+(.*))?$")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)\)")
_HTML = re.compile(r"<(?:[A-Za-z/!][^>]*)>")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)")
_LINK_SCHEMES = ("http://", "https://", "mailto:")


class AdfError(ValueError):
    def __init__(self, message: str, line: int):
        super().__init__(f"line {line}: {message}")
        self.line = line


def to_adf(markdown: str) -> dict:
    return {"type": "doc", "version": 1, "content": _Parser(markdown).blocks()}


@dataclass
class _Item:
    pieces: list[tuple[int, str]]
    children: list["_List"] = field(default_factory=list)


@dataclass
class _List:
    indent: int
    ordered: bool
    order: int
    items: list[_Item] = field(default_factory=list)


class _Parser:
    def __init__(self, markdown: str):
        self.lines = markdown.expandtabs(4).splitlines()
        self.out: list[dict] = []
        self.paragraph: list[tuple[int, str]] = []
        self.stack: list[_List] = []
        self.root: _List | None = None

    def blocks(self) -> list[dict]:
        index = 0
        while index < len(self.lines):
            index = self._line(index)
        self._flush()
        return self.out

    def _flush(self) -> None:
        self._flush_paragraph()
        self._flush_list()

    def _flush_paragraph(self) -> None:
        if self.paragraph:
            self.out.append(_paragraph(self.paragraph))
            self.paragraph = []

    def _flush_list(self) -> None:
        if self.root is not None:
            self.out.append(_build_list(self.root))
            self.root = None
            self.stack = []

    def _line(self, index: int) -> int:
        number = index + 1
        raw = self.lines[index].rstrip()
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())

        if not stripped:
            self._flush_paragraph()
            return number
        if stripped.startswith("```"):
            return self._fence(index, stripped[3:].strip())
        if stripped.startswith("|"):
            raise AdfError("table is not supported", number)
        if stripped.startswith(">"):
            raise AdfError("block quote is not supported", number)
        if _RULE.match(raw):
            raise AdfError("horizontal rule is not supported", number)
        if indent == 0 and (heading := _HEADING.match(raw)):
            self._flush()
            self.out.append(_heading(heading, number))
            return number
        if marker := _MARKER.match(raw):
            self._flush_paragraph()
            self._list_item(marker, number)
            return number
        if indent > 0 and self.stack:
            self.stack[-1].items[-1].pieces.append((number, stripped))
            return number
        self._flush_list()
        self.paragraph.append((number, stripped))
        return number

    def _fence(self, index: int, language: str) -> int:
        self._flush()
        number = index + 1
        if "`" in language:
            raise AdfError("code block fence is malformed", number)
        body: list[str] = []
        for end in range(index + 1, len(self.lines)):
            if self.lines[end].strip() == "```":
                node: dict = {"type": "codeBlock"}
                if language:
                    node["attrs"] = {"language": language}
                code = "\n".join(body)
                if code:
                    node["content"] = [{"type": "text", "text": code}]
                self.out.append(node)
                return end + 1
            body.append(self.lines[end])
        raise AdfError("code block is not closed", number)

    def _list_item(self, marker: re.Match, number: int) -> None:
        indent = len(marker.group(1))
        bullet = marker.group(2)
        ordered = bullet[0].isdigit()
        text = marker.group(3) or ""
        if checkbox := _CHECKBOX.match(text):
            symbol = CHECKED if checkbox.group(1) in "xX" else UNCHECKED
            text = f"{symbol} {checkbox.group(2) or ''}".rstrip()
        item = _Item([(number, text)])

        while self.stack and self.stack[-1].indent > indent:
            self.stack.pop()
        if self.stack and self.stack[-1].indent == indent:
            if self.stack[-1].ordered == ordered:
                self.stack[-1].items.append(item)
                return
            self.stack.pop()
        new = _List(indent, ordered, int(bullet[:-1]) if ordered else 1, [item])
        if self.stack:
            self.stack[-1].items[-1].children.append(new)
        else:
            self._flush_list()
            self.root = new
        self.stack.append(new)


def _heading(match: re.Match, number: int) -> dict:
    level = len(match.group(1))
    if level not in (2, 3):
        raise AdfError(f"heading level {level} is not supported (use ## or ###)", number)
    content = _inline_pieces([(number, match.group(2) or "")])
    if not content:
        raise AdfError("heading without text", number)
    return {"type": "heading", "attrs": {"level": level}, "content": content}


def _paragraph(pieces: list[tuple[int, str]]) -> dict:
    node: dict = {"type": "paragraph"}
    if content := _inline_pieces(pieces):
        node["content"] = content
    return node


def _build_list(source: _List) -> dict:
    items = []
    for item in source.items:
        content = [_paragraph(item.pieces), *(_build_list(child) for child in item.children)]
        items.append({"type": "listItem", "content": content})
    if source.ordered:
        return {"type": "orderedList", "attrs": {"order": source.order}, "content": items}
    return {"type": "bulletList", "content": items}


def _inline_pieces(pieces: list[tuple[int, str]]) -> list[dict]:
    nodes: list[dict] = []
    for position, (number, text) in enumerate(pieces):
        if position:
            nodes.append(_text(" ", ()))
        nodes.extend(_inline(text, number, ()))
    return _merge(nodes)


def _text(value: str, marks: tuple[dict, ...]) -> dict:
    node: dict = {"type": "text", "text": value}
    if marks:
        node["marks"] = [dict(mark) for mark in marks]
    return node


def _merge(nodes: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for node in nodes:
        if not node["text"]:
            continue
        if merged and merged[-1].get("marks") == node.get("marks"):
            merged[-1] = {**merged[-1], "text": merged[-1]["text"] + node["text"]}
        else:
            merged.append(node)
    return merged


def _inline(text: str, number: int, marks: tuple[dict, ...]) -> list[dict]:
    nodes: list[dict] = []
    buffer: list[str] = []

    def literal() -> None:
        plain = "".join(buffer)
        buffer.clear()
        if _HTML.search(plain):
            raise AdfError("raw HTML is not supported", number)
        if _ITALIC.search(plain):
            _check_italic(plain, number)
        if "~~" in plain:
            raise AdfError("strikethrough is not supported", number)
        nodes.append(_text(plain, marks))

    i = 0
    while i < len(text):
        char = text[i]
        if char == "`":
            end = text.find("`", i + 1)
            if end < 0:
                raise AdfError("inline code is not closed", number)
            literal()
            code_marks = tuple(m for m in marks if m["type"] != "strong") + ({"type": "code"},)
            nodes.append(_text(text[i + 1 : end], code_marks))
            i = end + 1
        elif text.startswith("**", i):
            end = text.find("**", i + 2)
            if end < 0:
                raise AdfError("bold is not closed", number)
            literal()
            nodes.extend(_inline(text[i + 2 : end], number, (*marks, {"type": "strong"})))
            i = end + 2
        elif char == "!" and text.startswith("![", i) and _LINK.match(text, i + 1):
            raise AdfError("image is not supported", number)
        elif char == "[" and (link := _LINK.match(text, i)):
            href = link.group(2)
            if not link.group(1).strip():
                raise AdfError("link without text", number)
            if not href.lower().startswith(_LINK_SCHEMES):
                raise AdfError("link must start with http://, https:// or mailto:", number)
            literal()
            mark = {"type": "link", "attrs": {"href": href}}
            nodes.extend(_inline(link.group(1), number, (*marks, mark)))
            i = link.end()
        else:
            buffer.append(char)
            i += 1
    literal()
    return nodes


def _check_italic(plain: str, number: int) -> None:
    positions = [m.start() for m in _ITALIC.finditer(plain)]
    for start, end in zip(positions, positions[1:], strict=False):
        between = plain[start + 1 : end]
        if between and not between[0].isspace() and not between[-1].isspace():
            raise AdfError("italic is not supported", number)


_SAMPLE = """## a
### b
text **b** `c` [d](https://example.com)
- [x] a
  1. b
```py
x
```"""


def producible_types() -> set[str]:
    return _types(to_adf(_SAMPLE))


def _types(node: dict) -> set[str]:
    found = {node["type"]}
    for mark in node.get("marks", []):
        found.add(mark["type"])
    for child in node.get("content", []):
        found |= _types(child)
    return found


def foreign_nodes(doc: dict) -> set[str]:
    return _types(doc) - producible_types()
