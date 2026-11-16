import pytest

from ws.database.guard import PLACEHOLDERS, WORDS, guard, split
from ws.database.port import Refused, Rules


@pytest.mark.parametrize(
    "sql",
    [
        "select count(*) from t where x in (4, 80)",
        "SELECT sum(amount) FROM t WHERE status = 'open'",
        "with x as (select id from t) select count(*) from x",
        "  select 1  ",
        "select coalesce(sum(a.v), 0) from a join b on a.id = b.a_id",
    ],
)
def test_guard_accepts_select_and_with(sql):
    assert guard(sql) == (sql.strip(), ())


def test_guard_drops_one_last_semicolon():
    assert guard("select 1;") == ("select 1", ())
    assert guard("select 1 ;  \n") == ("select 1", ())


@pytest.mark.parametrize(
    "sql",
    [
        "select 1; select 2",
        "select 1;;",
        "select 1; delete from t",
        "select ';'; select 2",
    ],
)
def test_guard_refuses_two_statements(sql):
    with pytest.raises(Refused, match="^only one statement is allowed$"):
        guard(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "select count(*) from t where a = 'x;y'",
        "select count(*) from t where a = 'it''s;'",
        'select count(*) from "we;ird"',
        "select count(*) from t where a = 'x;y';",
    ],
)
def test_guard_semicolon_inside_a_literal_or_identifier(sql):
    assert guard(sql)[0] == sql.removesuffix(";")


@pytest.mark.parametrize(
    ("sql", "word"),
    [
        ("delete from t", None),
        ("select 1 into t2", "into"),
        ("select a into t2 from t", "into"),
        ("with x as (delete from t returning 1) select count(*) from x", "delete"),
        ("with x as (update t set a = 1 returning 1) select count(*) from x", "update"),
        ("with x as (insert into t values (1) returning 1) select count(*) from x", "insert"),
        ("select count(*) from t for update", "update"),
        ("select count(*) from t; set role admin", None),
        ("with x as (select 1) merge into t using x on true when matched then delete", "merge"),
        ("select 1 from t where exists (select 1 from u) and Truncate", "truncate"),
        ("select count(*) from t where a = 1 and lock", "lock"),
        ("select count(*) from t where execute", "execute"),
        ("select \"set_config\"('a', 'b', false)", "set_config"),
        ('select "SET"(1)', "set"),
    ],
)
def test_guard_refuses_write_words(sql, word):
    rules = Rules(words=("set_config",))
    with pytest.raises(Refused) as caught:
        guard(sql, rules)
    if word is not None:
        assert str(caught.value).startswith(f'"{word}" is not allowed outside a literal')


@pytest.mark.parametrize(
    "sql",
    [
        "select count(*) from t where status = 'delete'",
        'select "update" from t',
        "select count(*) from t where note = 'select 1 into t2; drop table t'",
        "select count(*) from updated_rows",
        "select count(*) from t where t.created_at > now() - interval '1 day'",
        'select count(*) from t where "into" = 1',
        "select count(*) from t where replace(a, 'x', '') = 'y'",
    ],
)
def test_guard_keeps_words_in_literals_and_identifiers(sql):
    assert guard(sql)[0] == sql


def test_guard_words_cover_writes_schema_and_session():
    assert {"insert", "update", "delete", "into", "set", "begin", "execute"} <= set(WORDS)
    assert "replace" not in WORDS


@pytest.mark.parametrize(
    "sql",
    ["select count(*) from t where comment = 'x'", "select count(*) from t where t.comment = 'x'"],
)
def test_guard_word_refusal_says_how_to_name_a_column(sql):
    rules = Rules(words=("comment",))
    with pytest.raises(Refused) as caught:
        guard(sql, rules)
    assert str(caught.value) == (
        '"comment" is not allowed outside a literal; '
        'quote it and drop the table qualifier: "comment"'
    )
    quoted = "select count(*) from t where \"comment\" = 'x'"
    assert guard(quoted, rules)[0] == quoted


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("select query_to_xml('select 1', true, false, '')", "words starting with query_to_"),
        ("select count(*) from t where query_to_xml ('x')", "words starting with query_to_"),
        ("select count(*) from t where cleanup()", '"cleanup"'),
        ("select count(*) from t where cleanup\n(1)", '"cleanup"'),
    ],
)
def test_guard_function_call_gets_no_column_hint(sql, reason):
    rules = Rules(words=("cleanup",), prefixes=("query_to_",))
    with pytest.raises(Refused) as caught:
        guard(sql, rules)
    assert str(caught.value).startswith(reason)
    assert "quote it" not in str(caught.value)
    assert ";" not in str(caught.value)


@pytest.mark.parametrize(
    "sql",
    [
        "select 1) union all select (2",
        "select s from t where a = 1) as x, (0",
        "select (1",
        "select count(*) from t where (a = 1",
        "select count(*) from t where a = 1)",
        "select count(*) from t where a in (1, 2)) or (b = 3",
    ],
)
def test_guard_refuses_unbalanced_parentheses(sql):
    with pytest.raises(Refused) as caught:
        guard(sql)
    assert str(caught.value) == "parentheses are not balanced"


@pytest.mark.parametrize(
    "sql",
    [
        "select count(*) from t where a = ')'",
        "select count(*) from t where a = '(' and b in (select c from u where d = ')(')",
        'select count(*) from "a(b" where (x = 1)',
    ],
)
def test_guard_counts_parentheses_outside_quotes_only(sql):
    assert guard(sql)[0] == sql


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("select 1 -- x", "comments are not allowed"),
        ("select /* x */ 1", "comments are not allowed"),
        ("select 1 --", "comments are not allowed"),
        ("select 1; -- x", "comments are not allowed"),
        ("", "the query is empty"),
        ("   ", "the query is empty"),
        (" ;", "the query is empty"),
        ("select 'x", "unclosed literal or quoted identifier"),
        ('select "x', "unclosed literal or quoted identifier"),
        ("select 'it''s", "unclosed literal or quoted identifier"),
        ("values (1)", "the query must start with select or with"),
        ("(select 1)", "the query must start with select or with"),
        ("'select' 1", "the query must start with select or with"),
        ("copy t to stdout", "the query must start with select or with"),
        ("set statement_timeout = 0", "the query must start with select or with"),
        ("explain analyze delete from t", "the query must start with select or with"),
    ],
)
def test_guard_refuses_comments_empty_and_unclosed(sql, reason):
    with pytest.raises(Refused) as caught:
        guard(sql)
    assert str(caught.value) == reason


@pytest.mark.parametrize(
    "sql",
    [
        "select count(*) from t where note = '-- not a comment /* nor this */'",
        'select count(*) from "a--b"',
        "select 5 - -1",
    ],
)
def test_guard_comment_marks_inside_quotes_are_text(sql):
    assert guard(sql)[0] == sql


def test_guard_lists_placeholders():
    sql = "select count(*) from t where u >= :day_from and u < :day_to"
    assert guard(sql) == (sql, ("day_from", "day_to"))
    assert guard("select count(*) from t where u < :day_to and d = :day")[1] == ("day", "day_to")
    assert guard("select x::numeric from t")[1] == ()
    assert guard("select count(*) from t where a = ':day'")[1] == ()
    assert PLACEHOLDERS == ("day", "day_from", "day_to")


def test_guard_refuses_an_unknown_placeholder():
    with pytest.raises(Refused) as caught:
        guard("select count(*) from t where u < :other")
    assert str(caught.value) == "unknown placeholder :other; use :day, :day_from or :day_to"


@pytest.mark.parametrize(
    "sql",
    ["select count(*) from t where u < :'day_to'", 'select count(*) from :"t"'],
)
def test_guard_refuses_a_colon_before_a_quote(sql):
    with pytest.raises(Refused) as caught:
        guard(sql)
    assert str(caught.value) == (
        "quoted placeholders are not allowed; use :day, :day_from or :day_to"
    )


def test_guard_accepts_a_cast_to_a_quoted_type():
    sql = "select count(*) from t where a::\"char\" = 'x'"
    assert guard(sql) == (sql, ())


@pytest.mark.parametrize(
    "sql",
    ["select 1:::USER", "select 1:::'USER'", 'select 1:::"USER"', "select x::::numeric from t"],
)
def test_guard_refuses_three_colons(sql):
    with pytest.raises(Refused) as caught:
        guard(sql)
    assert str(caught.value) == "three or more colons in a row are not allowed; use :: for a cast"


@pytest.mark.parametrize("sql", ["select :{?day}", "select count(*) from t where :{?HOST}"])
def test_guard_refuses_braced_placeholders(sql):
    with pytest.raises(Refused) as caught:
        guard(sql)
    assert str(caught.value) == (
        "placeholders with braces are not allowed; use :day, :day_from or :day_to"
    )


RULES = Rules(words=("vacuum",), prefixes=("pg_",), marks=("\\",))


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("select pg_sleep(1)", "words starting with pg_ are not allowed"),
        ("select PG_SLEEP(1)", "words starting with pg_ are not allowed"),
        ("select pg_catalog.now()", "words starting with pg_ are not allowed"),
        ('select "pg_sleep"(1)', "words starting with pg_ are not allowed"),
        ('select "pg_sleep" (1)', "words starting with pg_ are not allowed"),
        ("select 1 \\gexec", '"\\" is not allowed'),
        ("select count(*) from t where a = E'\\''", '"\\" is not allowed'),
        ('select count(*) from "a\\b"', '"\\" is not allowed'),
        ("vacuum", "the query must start with select or with"),
        ("select 1 from t where vacuum", '"vacuum" is not allowed outside a literal'),
    ],
)
def test_guard_applies_rules(sql, reason):
    with pytest.raises(Refused) as caught:
        guard(sql, RULES)
    assert str(caught.value).startswith(reason)


@pytest.mark.parametrize(
    "sql",
    [
        'select (1.5)."pg_sleep"',
        'select (1.5) . "pg_sleep"',
        'select (1.5).U&"pg_sleep"',
        'select count(*) from t where ("a")."pg_x" > 0',
        'select "pg_catalog"."pg_sleep"',
        'select (1)."vacuum"',
        'select (1)."VACUUM"',
    ],
)
def test_guard_checks_a_quoted_name_after_a_dot(sql):
    with pytest.raises(Refused) as caught:
        guard(sql, RULES)
    assert str(caught.value) in (
        "words starting with pg_ are not allowed",
        '"vacuum" is not allowed outside a literal',
    )


QUOTED_RULES = Rules(words=("vacuum", "comment"), prefixes=("pg_", "brin_"))


@pytest.mark.parametrize(
    ("sql", "prefix"),
    [
        ('select count(*) from "pg_stat_activity"', "pg_"),
        ('select count(*) from "PG_STAT_ACTIVITY"', "pg_"),
        ('select count(*) from "Pg_Stat_Activity"', "pg_"),
        ('select count(*) from "pg_""x"', "pg_"),
        ('select "pg_x" from t', "pg_"),
        ('select count(*) from s."pg_x"', "pg_"),
        ('select count(*) from t where "brin_summarize_new_values" is null', "brin_"),
    ],
)
def test_guard_checks_the_prefixes_on_every_quoted_name(sql, prefix):
    with pytest.raises(Refused) as caught:
        guard(sql, QUOTED_RULES)
    assert str(caught.value) == f"words starting with {prefix} are not allowed"


@pytest.mark.parametrize(
    "sql",
    [
        "select count(*) from t where \"comment\" = 'x'",
        'select count(*) from t where "COMMENT" is not null',
        'select "vacuum" from t',
    ],
)
def test_guard_keeps_a_quoted_engine_word_used_as_a_column(sql):
    assert guard(sql, QUOTED_RULES)[0] == sql


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("select count(*) from t where a = 1 and lock", '"lock" is not allowed outside a literal'),
        ("select count(*) from t where delete", '"delete" is not allowed outside a literal'),
        ("select count(*) from pg_stat_activity", "words starting with pg_ are not allowed"),
        ("select count(*) from t where brin_x > 0", "words starting with brin_ are not allowed"),
        ("select count(*) from t where vacuum(1) > 0", '"vacuum" is not allowed outside a literal'),
    ],
)
def test_guard_gives_the_column_hint_only_to_an_engine_word(sql, message):
    with pytest.raises(Refused) as caught:
        guard(sql, QUOTED_RULES)
    assert str(caught.value) == message


def test_guard_gives_no_column_hint_to_a_word_that_quoting_would_not_save():
    rules = Rules(words=("dblink",), prefixes=("dblink",))
    with pytest.raises(Refused) as caught:
        guard("select count(*) from t where dblink = 1", rules)
    assert str(caught.value) == '"dblink" is not allowed outside a literal'


@pytest.mark.parametrize(
    "sql",
    [
        "select count(*) from t where a = 'pg_sleep(1); vacuum'",
        "select count(*) from my_pg_table",
        'select count(*) from s."t" where t."id" > 0',
    ],
)
def test_guard_rules_skip_quotes(sql):
    assert guard(sql, RULES)[0] == sql


def test_split_keeps_quotes_and_escapes():
    sql = "select 'a''b;' from \"x\"\"y\" where z = ''"
    assert split(sql) == [
        ("code", "select "),
        ("literal", "'a''b;'"),
        ("code", " from "),
        ("identifier", '"x""y"'),
        ("code", " where z = "),
        ("literal", "''"),
    ]
    assert "".join(text for _, text in split(sql)) == sql


def test_split_of_mixed_quotes():
    assert split("select '\"' , \"'\"") == [
        ("code", "select "),
        ("literal", "'\"'"),
        ("code", " , "),
        ("identifier", '"\'"'),
    ]
    assert split("") == []


@pytest.mark.parametrize("sql", ["select 'x", 'select "x', "select 'a''"])
def test_split_refuses_unclosed(sql):
    with pytest.raises(Refused, match="^unclosed literal or quoted identifier$"):
        split(sql)
