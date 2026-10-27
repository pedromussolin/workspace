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
        self.lines = markdown.splitlines()
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
        raw = self.lines[index].expandtabs(4).rstrip()
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())

        if not stripped:
            self._flush_paragraph()
            return number
        if stripped.startswith("```"):
            if indent > 0 and self.stack:
                raise AdfError("code block inside a list item is not supported", number)
            return self._fence(index, stripped[3:].strip())
        if stripped.startswith("|"):
            raise AdfError("table is not supported", number)
        if stripped.startswith(">"):
            raise AdfError("block quote is not supported", number)
        if _RULE.match(raw):
            raise AdfError("horizontal rule is not supported", number)
        if indent <= 3 and (heading := _HEADING.match(stripped)):
            self._flush()
            self.out.append(_heading(heading, number))
            return number
        marker = _MARKER.match(raw)
        if marker and marker.group(2)[0].isdigit() and not marker.group(3):
            marker = None
        if marker:
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
        _refuse_block_markup(text, number)
        if checkbox := _CHECKBOX.match(text):
            _refuse_block_markup(checkbox.group(2) or "", number)
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


def _refuse_block_markup(text: str, number: int) -> None:
    if text.startswith("|"):
        raise AdfError("table is not supported", number)
    if text.startswith(">"):
        raise AdfError("block quote is not supported", number)
    if text.startswith("```"):
        raise AdfError("code block inside a list item is not supported", number)
    if _RULE.match(text):
        raise AdfError("horizontal rule is not supported", number)
    if _HEADING.match(text):
        raise AdfError("heading inside a list item is not supported", number)


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
    text = " ".join(piece for _, piece in pieces)
    starts = []
    offset = 0
    for number, piece in pieces:
        starts.append((offset, number))
        offset += len(piece) + 1

    def locate(position: int) -> int:
        return [number for start, number in starts if start <= position][-1]

    _check_italic(text, locate)
    return _merge(_inline(text, 0, locate, ()))


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


def _inline(text: str, base: int, locate, marks: tuple[dict, ...]) -> list[dict]:
    nodes: list[dict] = []
    buffer: list[str] = []
    buffer_start = 0

    def literal() -> None:
        plain = "".join(buffer)
        buffer.clear()
        if html := _HTML.search(plain):
            raise AdfError("raw HTML is not supported", locate(base + buffer_start + html.start()))
        if "~~" in plain:
            raise AdfError(
                "strikethrough is not supported", locate(base + buffer_start + plain.index("~~"))
            )
        nodes.append(_text(plain, marks))

    i = 0
    while i < len(text):
        char = text[i]
        here = locate(base + i)
        if char == "`":
            end = text.find("`", i + 1)
            if end < 0:
                raise AdfError("inline code is not closed", here)
            literal()
            code_marks = tuple(m for m in marks if m["type"] != "strong") + ({"type": "code"},)
            nodes.append(_text(text[i + 1 : end], code_marks))
            i = end + 1
            buffer_start = i
        elif text.startswith("**", i):
            end = text.find("**", i + 2)
            if end < 0:
                raise AdfError("bold is not closed", here)
            literal()
            strong = (*marks, {"type": "strong"})
            nodes.extend(_inline(text[i + 2 : end], base + i + 2, locate, strong))
            i = end + 2
            buffer_start = i
        elif char == "!" and text.startswith("![", i) and _LINK.match(text, i + 1):
            raise AdfError("image is not supported", here)
        elif char == "[" and (link := _LINK.match(text, i)):
            href = link.group(2)
            if not link.group(1).strip():
                raise AdfError("link without text", here)
            if "(" in href:
                raise AdfError("link address with parentheses is not supported", here)
            if not href.lower().startswith(_LINK_SCHEMES):
                raise AdfError("link must start with http://, https:// or mailto:", here)
            literal()
            mark = {"type": "link", "attrs": {"href": href}}
            inner = _inline(link.group(1), base + i + 1, locate, (*marks, mark))
            nodes.extend(inner)
            i = link.end()
            buffer_start = i
        else:
            if not buffer:
                buffer_start = i
            buffer.append(char)
            i += 1
    literal()
    return nodes


def _check_italic(text: str, locate) -> None:
    kept: list[tuple[str, int]] = []
    i = 0
    while i < len(text):
        if text[i] == "`":
            end = text.find("`", i + 1)
            i = len(text) if end < 0 else end + 1
        elif text.startswith("**", i):
            i += 2
        else:
            kept.append((text[i], i))
            i += 1
    flat = "".join(char for char, _ in kept)
    marks = [k for k, (char, _) in enumerate(kept) if char == "*"]
    for first, second in zip(marks, marks[1:], strict=False):
        between = flat[first + 1 : second]
        if between and not between[0].isspace() and not between[-1].isspace():
            raise AdfError("italic is not supported", locate(kept[first][1]))


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
