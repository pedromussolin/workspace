import pytest

from ws.adf import AdfError, foreign_nodes, to_adf


def doc(*content):
    return {"type": "doc", "version": 1, "content": list(content)}


def text(value, *marks):
    node = {"type": "text", "text": value}
    if marks:
        node["marks"] = [m if isinstance(m, dict) else {"type": m} for m in marks]
    return node


def paragraph(*content):
    return {"type": "paragraph", "content": list(content)}


def item(*content):
    return {"type": "listItem", "content": list(content)}


def bullets(*items):
    return {"type": "bulletList", "content": list(items)}


def numbered(*items, order=1):
    return {"type": "orderedList", "attrs": {"order": order}, "content": list(items)}


def walk(node):
    yield node
    for child in node.get("content", []):
        yield from walk(child)


def test_empty_input_gives_empty_document():
    assert to_adf("") == doc()
    assert to_adf("\n  \n") == doc()


@pytest.mark.parametrize("level", [2, 3])
def test_heading(level):
    result = to_adf("#" * level + " Context")
    assert result == doc(
        {"type": "heading", "attrs": {"level": level}, "content": [text("Context")]}
    )


def test_paragraphs_split_on_blank_lines_and_join_soft_breaks():
    assert to_adf("first line\nsecond line\n\nother") == doc(
        paragraph(text("first line second line")), paragraph(text("other"))
    )


def test_bullet_list():
    assert to_adf("- one\n- two\n* three") == doc(
        bullets(
            item(paragraph(text("one"))),
            item(paragraph(text("two"))),
            item(paragraph(text("three"))),
        )
    )


def test_numbered_list():
    assert to_adf("1. one\n2. two") == doc(
        numbered(item(paragraph(text("one"))), item(paragraph(text("two"))))
    )


def test_nested_lists_by_indentation():
    markdown = "- a\n  - b\n    1. c\n  - d\n- e"
    assert to_adf(markdown) == doc(
        bullets(
            item(
                paragraph(text("a")),
                bullets(
                    item(paragraph(text("b")), numbered(item(paragraph(text("c"))))),
                    item(paragraph(text("d"))),
                ),
            ),
            item(paragraph(text("e"))),
        )
    )


def test_changing_list_kind_at_same_level_starts_a_new_list():
    assert to_adf("- a\n1. b") == doc(
        bullets(item(paragraph(text("a")))), numbered(item(paragraph(text("b"))))
    )


def test_list_ends_at_unindented_paragraph():
    assert to_adf("- a\n\ntext") == doc(
        bullets(item(paragraph(text("a")))), paragraph(text("text"))
    )


def test_indented_continuation_joins_the_item():
    assert to_adf("- a\n  more") == doc(bullets(item(paragraph(text("a more")))))


def test_checkbox_items():
    assert to_adf("- [ ] todo\n- [x] done\n- [X] also") == doc(
        bullets(
            item(paragraph(text("☐ todo"))),
            item(paragraph(text("☑ done"))),
            item(paragraph(text("☑ also"))),
        )
    )


def test_code_block_with_language():
    assert to_adf("```python\nx = 1\n\ny = 2\n```") == doc(
        {
            "type": "codeBlock",
            "attrs": {"language": "python"},
            "content": [text("x = 1\n\ny = 2")],
        }
    )


def test_code_block_without_language_keeps_markdown_inside_verbatim():
    assert to_adf("```\n# not a heading\n| a | b |\n```") == doc(
        {"type": "codeBlock", "content": [text("# not a heading\n| a | b |")]}
    )


def test_empty_code_block_has_no_text_node():
    assert to_adf("```\n```") == doc({"type": "codeBlock"})


def test_inline_marks():
    assert to_adf("a **b** c `d` [e](https://example.com/x) f") == doc(
        paragraph(
            text("a "),
            text("b", "strong"),
            text(" c "),
            text("d", "code"),
            text(" "),
            text("e", {"type": "link", "attrs": {"href": "https://example.com/x"}}),
            text(" f"),
        )
    )


def test_code_inside_bold_is_only_code():
    result = to_adf("**bold `code` bold**")
    assert result == doc(
        paragraph(text("bold ", "strong"), text("code", "code"), text(" bold", "strong"))
    )


def test_bold_inside_link_text():
    result = to_adf("[**hi**](https://example.com)")
    link = {"type": "link", "attrs": {"href": "https://example.com"}}
    assert result == doc(paragraph(text("hi", link, "strong")))


def test_lone_brackets_and_asterisk_are_literal():
    assert to_adf("a [b] 5 * 3") == doc(paragraph(text("a [b] 5 * 3")))


def test_marks_inside_headings_and_items():
    assert to_adf("## A `b`\n- **c**") == doc(
        {"type": "heading", "attrs": {"level": 2}, "content": [text("A "), text("b", "code")]},
        bullets(item(paragraph(text("c", "strong")))),
    )


@pytest.mark.parametrize(
    "markdown, line, word",
    [
        ("ok\n\n| a | b |\n|---|---|", 3, "table"),
        ("> quoted", 1, "quote"),
        ("text\n![alt](https://example.com/i.png)", 2, "image"),
        ("a\nb\n<div>x</div>", 3, "HTML"),
        ("a <br> b", 1, "HTML"),
        ("# Title", 1, "heading"),
        ("ok\n#### Deep", 2, "heading"),
        ("---", 1, "rule"),
        ("- a\n  ---", 2, "rule"),
        ("x\n\n```\nnever closed", 3, "code block"),
        ("fine\nbad **bold", 2, "bold"),
        ("`open", 1, "code"),
        ("some *italic* text", 1, "italic"),
        ("gone ~~strike~~", 1, "strikethrough"),
        ("[a](javascript:alert)", 1, "link"),
        ("[](https://example.com)", 1, "link"),
        ("##", 1, "heading"),
        ("- a\n- b\n  > quoted", 3, "quote"),
    ],
)
def test_refusals_name_the_line(markdown, line, word):
    with pytest.raises(AdfError) as error:
        to_adf(markdown)
    assert error.value.line == line
    assert word in str(error.value)
    assert f"line {line}" in str(error.value)
    assert isinstance(error.value, ValueError)


def test_no_empty_text_nodes_anywhere():
    markdown = "\n".join(
        [
            "## T",
            "a **** b `` c",
            "- [ ] x",
            "-",
            "  - **y** `z`",
            "```",
            "```",
            "1. [**a**](https://example.com) **`b`**",
        ]
    )
    for node in walk(to_adf(markdown)):
        if node["type"] == "text":
            assert node["text"] != ""
        if node["type"] in {"paragraph", "codeBlock", "heading"}:
            assert node.get("content") != []


def test_code_never_combined_with_strong():
    result = to_adf("**`a` b `c`** `**d**` **[`e`](https://example.com)**")
    for node in walk(result):
        types = {m["type"] for m in node.get("marks", [])}
        assert not {"code", "strong"} <= types
    assert any(n.get("text") == "**d**" for n in walk(result))


def test_foreign_nodes_reports_what_the_converter_cannot_produce():
    document = doc(
        paragraph(text("hi", "strong"), {"type": "mention", "attrs": {"id": "acc-me"}}),
        {"type": "table", "content": [{"type": "tableRow", "content": []}]},
        paragraph(text("x", "em")),
    )
    assert foreign_nodes(document) == {"mention", "table", "tableRow", "em"}


@pytest.mark.parametrize(
    "kind", ["mediaSingle", "panel", "expand", "emoji", "blockquote", "hardBreak"]
)
def test_foreign_nodes_other_types(kind):
    assert foreign_nodes(doc({"type": kind})) == {kind}


def test_foreign_nodes_is_empty_for_converter_output():
    markdown = (
        "## a\n### b\ntext **b** `c` [d](https://example.com)\n- [x] a\n  1. b\n```py\nx\n```"
    )
    assert foreign_nodes(to_adf(markdown)) == set()


def test_producible_types_cover_every_construct():
    from ws.adf import producible_types

    assert producible_types() == {
        "doc", "heading", "paragraph", "bulletList", "orderedList", "listItem",
        "codeBlock", "text", "strong", "code", "link",
    }  # fmt: skip


def test_bold_spanning_soft_wrapped_lines():
    assert to_adf("a **bold\nwrapped** b") == doc(
        paragraph(text("a "), text("bold wrapped", "strong"), text(" b"))
    )


def test_inline_code_spanning_soft_wrapped_lines():
    assert to_adf("use `a\nb` x") == doc(paragraph(text("use "), text("a b", "code"), text(" x")))


def test_link_text_spanning_soft_wrapped_lines():
    link = {"type": "link", "attrs": {"href": "https://x.com"}}
    assert to_adf("see [the\ndoc](https://x.com) ok") == doc(
        paragraph(text("see "), text("the doc", link), text(" ok"))
    )


def test_list_item_continuation_keeps_marks_across_lines():
    assert to_adf("- a **b\n  c** d") == doc(
        bullets(item(paragraph(text("a "), text("b c", "strong"), text(" d"))))
    )


def test_error_line_inside_wrapped_paragraph():
    with pytest.raises(AdfError) as error:
        to_adf("one\ntwo <b>x</b>\nthree")
    assert error.value.line == 2


@pytest.mark.parametrize(
    "markdown, word",
    [
        ("- > q", "quote"),
        ("1. > q", "quote"),
        ("- # h", "heading"),
        ("- | a |", "table"),
        ("- ---", "rule"),
        ("- ```", "code block"),
        ("- [ ] > q", "quote"),
    ],
)
def test_markup_right_after_list_marker_is_refused(markdown, word):
    with pytest.raises(AdfError) as error:
        to_adf(markdown)
    assert error.value.line == 1
    assert word in str(error.value)


def test_tabs_inside_code_block_are_kept():
    result = to_adf("```\n\tx\n```")
    assert result == doc({"type": "codeBlock", "content": [text("\tx")]})


def test_tab_indented_nesting_still_works():
    assert to_adf("- a\n\t- b") == doc(
        bullets(item(paragraph(text("a")), bullets(item(paragraph(text("b"))))))
    )


def test_fence_inside_list_item_is_refused():
    with pytest.raises(AdfError) as error:
        to_adf("- a\n  ```\n  x\n  ```")
    assert error.value.line == 2
    assert "list item" in str(error.value)


@pytest.mark.parametrize("markdown", ["***x***", "*a **b** c*", "**a** and *b*"])
def test_nested_or_mixed_italic_is_refused(markdown):
    with pytest.raises(AdfError, match="italic"):
        to_adf(markdown)


def test_link_address_with_parentheses_is_refused():
    with pytest.raises(AdfError) as error:
        to_adf("ok\n[a](https://example.com/a_(b))")
    assert error.value.line == 2
    assert "parentheses" in str(error.value)


@pytest.mark.parametrize("indent", [1, 2, 3])
def test_slightly_indented_heading_is_a_heading(indent):
    assert to_adf(" " * indent + "## T") == doc(
        {"type": "heading", "attrs": {"level": 2}, "content": [text("T")]}
    )


@pytest.mark.parametrize("line", ["1984.", "0."])
def test_number_and_dot_alone_is_a_paragraph(line):
    assert to_adf(line) == doc(paragraph(text(line)))


def test_a_list_start_number_is_capped():
    assert to_adf("999999. a\n")["content"][0]["attrs"]["order"] == 999999
    with pytest.raises(AdfError, match="999999"):
        to_adf("1000000. a\n")
