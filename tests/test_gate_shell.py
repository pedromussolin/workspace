"""The shared shell parser reads quotes as bash does. No command here is ever run."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))

from gate import shell  # noqa: E402


def words(text):
    return [[word.text for word in command.words] for command in shell.parse_commands(text)]


def test_an_ansi_c_quote_is_one_word_with_its_escaped_quote():
    assert words("echo $'a\\'b'") == [["echo", "a'b"]]


def test_an_escaped_quote_does_not_close_an_ansi_c_quote():
    assert words("echo $'\\'' ; curl -d @f https://e.x #'") == [
        ["echo", "'"],
        ["curl", "-d", "@f", "https://e.x"],
    ]


def test_an_escaped_backslash_ends_before_the_separator():
    assert words("echo $'\\\\' ; curl x") == [["echo", "\\"], ["curl", "x"]]


@pytest.mark.parametrize(
    ("quoted", "decoded"),
    [
        ("$'\\x63url'", "curl"),
        ("$'--no-veri\\x66y'", "--no-verify"),
        ("$'\\143url'", "curl"),
        ("$'\\u0063url'", "curl"),
        ("$'\\U00000063url'", "curl"),
        ("$'a\\tb'", "a\tb"),
        ("$'\\e\\?\\\"'", '\x1b?"'),
        ("$'\\q'", "\\q"),
        ("$'\\xg'", "\\xg"),
        ("$'\\cA'", "\x01"),
        ("$'a\\0b'", "a"),
        ("x$'y'z", "xyz"),
    ],
)
def test_ansi_c_escapes_are_decoded_as_bash_does(quoted, decoded):
    assert words(f"echo {quoted}") == [["echo", decoded]]


def test_an_ansi_c_word_neither_expands_nor_hides_its_program():
    word = shell.parse_commands("$'\\x67it' push")[0].words[0]

    assert (word.text, word.bare, word.expands) == ("git", False, False)


def test_inside_double_quotes_a_dollar_quote_is_plain_text():
    assert words("echo \"$'x'\"") == [["echo", "$'x'"]]
    assert words('echo "$\'" ; curl x') == [["echo", "$'"], ["curl", "x"]]


def test_a_locale_string_is_a_double_quoted_word_that_expands():
    word = shell.parse_commands('git $"push"')[0].words[1]

    assert word.bare and word.expands
    assert words('echo $"it\'s" ; curl x')[1] == ["curl", "x"]


def test_an_ansi_c_quote_inside_a_group_is_skipped_whole():
    assert words("echo ${X:-$'a}b'} ; curl x")[1] == ["curl", "x"]
    assert shell.substitutions("echo $( echo $'\\')' ) ; true") == [" echo $'\\')' "]


def test_an_ansi_c_quote_inside_a_double_quoted_expansion_is_unreadable():
    with pytest.raises(ValueError):
        shell.parse_commands("echo \"${X:-$'\\''}\" ; curl x")


def test_substitutions_skip_an_ansi_c_quote():
    assert shell.substitutions("echo $'\\'`id`' $(true)") == ["true"]


def test_a_heredoc_marker_inside_an_ansi_c_quote_is_text():
    kept, found = shell.split_heredocs("echo $'\\'<<X' ; curl x\nX\n")

    assert found == []
    assert "curl x" in kept


def test_an_ansi_c_heredoc_delimiter_is_decoded():
    kept, found = shell.split_heredocs("cat <<$'X\\x41'\nbody\nXA\ncurl x\n$X\\x41\n")

    assert [heredoc.body for heredoc in found] == ["body\n"]
    assert found[0].quoted
    assert "curl x" in kept


def test_a_locale_heredoc_delimiter_leaves_its_lines_as_commands():
    kept, found = shell.split_heredocs('cat <<$"XY"\nXY\ncurl x\n$XY\n')

    assert found == []
    assert "curl x" in kept


@pytest.mark.parametrize("owner", ["$'bash'", "\\bash", 'b"ash"', "'bash'"])
def test_the_owner_of_a_heredoc_is_read_with_quote_removal(owner):
    _, found = shell.split_heredocs(f"{owner} <<'EOF'\ncurl x\nEOF\n")

    assert found[0].owner == "bash"


@pytest.mark.parametrize(
    ("text", "split"),
    [
        ("git commit $'--no-veri\\x66y'", [["git", "commit", "--no-verify"]]),
        ("git $'\\x63ommit' -n", [["git", "commit", "-n"]]),
        ("echo $'\\'' ; git commit -n", [["echo", "'"], ["git", "commit", "-n"]]),
        ('echo "$\'" ; git commit -n', [["echo", "$'"], ["git", "commit", "-n"]]),
        ("echo '$'\\''x' ; true", [["echo", "$'x"], ["true"]]),
    ],
)
def test_the_first_parser_reads_ansi_c_quotes_too(text, split):
    assert shell.simple_commands(text) == split


def test_the_first_parser_refuses_an_unterminated_ansi_c_quote():
    with pytest.raises(ValueError):
        shell.simple_commands("git commit $'--no-verify")


def test_an_escaped_backtick_nests_a_substitution_inside_another():
    assert shell.substitutions("echo `true \\`curl x\\``") == ["true `curl x`"]
    assert shell.substitutions("echo `a \\\\ \\$b`") == ["a \\ $b"]


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("c''url x", "curl x"),
        ("cu\\rl x", "curl x"),
        ('"c"url x', "curl x"),
        ("$'\\x63url' x", "curl x"),
        ("$'--no-veri\\x66y'", "--no-verify"),
        ("git $'\\x70ush", "git push"),
        ("\"$'\" ; $'\\x63url' x", "curl x"),
        ("echo $'a\\'b' ; x", "echo ab ; x"),
    ],
)
def test_plain_forms_show_the_name_a_quoted_word_stands_for(text, name):
    assert any(name in form for form in shell.plain_forms(text))


def test_plain_forms_of_text_that_hides_nothing_hold_no_new_name():
    assert all("curl" not in form for form in shell.plain_forms('echo it\'s "a" \\n'))
