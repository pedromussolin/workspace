import pytest

from ws.names import (
    Name,
    NamesTable,
    NamesTableMissing,
    find_blocked_domains,
    find_real_names,
    load_names,
    mask_text,
)


def test_longest_first(table):
    assert mask_text("Acme Capital e Acme", table) == "Summit Partners e Apex"


def test_word_boundary(table):
    assert find_real_names("Acmeville", table) == []
    assert find_real_names("acmeville", table) == []
    assert find_real_names("preacme", table) == []
    assert find_real_names("(Acme)", table) == ["Acme"]


@pytest.mark.parametrize(
    ("text", "masked"),
    [
        ("acme_theme: x", "apex_theme: x"),
        ("theme_acme", "theme_apex"),
        ("AcmeTheme", "ApexTheme"),
        ("themeAcme", "themeApex"),
        ("ACME_API_URL=x", "APEX_API_URL=x"),
        ("acme2", "apex2"),
        ("v2acme", "v2apex"),
        ("theme-acme", "theme-apex"),
        ("MéridiaTheme meridia_x", "MeridianaTheme meridiana_x"),
    ],
)
def test_names_inside_identifiers(table, text, masked):
    assert find_real_names(text, table) != []
    assert mask_text(text, table) == masked
    assert find_real_names(masked, table) == []


def test_identifier_matches_report_only_the_name(table):
    assert find_real_names("AcmeTheme and ACME_API", table) == ["Acme", "ACME"]


def test_longer_word_that_merely_starts_with_a_name_still_passes(table):
    for text in ("Acmeville_theme", "AcmevilleTheme", "acmeville2", "ACMEVILLE_URL"):
        assert find_real_names(text, table) == []


def test_accent_insensitive(table):
    assert find_real_names("Meridia", table) == ["Meridia"]
    assert find_real_names("méridia", table) == ["méridia"]
    assert find_real_names("MÉRIDIA", table) == ["MÉRIDIA"]


def test_accent_insensitive_decomposed_text(table):
    decomposed = "Me\u0301ridia"
    assert find_real_names(decomposed, table) == [decomposed]
    assert mask_text(decomposed, table) == "Meridiana"


def test_accent_insensitive_term_without_accent():
    accented = NamesTable((Name("Acme", "Apex"),), ())
    assert find_real_names("Acmé", accented) == ["Acmé"]


def test_case_shape(table):
    assert mask_text("acme ACME Acme", table) == "apex APEX Apex"
    assert mask_text("méridia MÉRIDIA Méridia", table) == "meridiana MERIDIANA Meridiana"


def test_case_sensitive_entry(table):
    assert find_real_names("brilliant idea", table) == []
    assert find_real_names("Brilliant", table) == ["Brilliant"]
    assert find_real_names("bRILLIANT", table) == []


def test_case_sensitive_entry_also_matches_its_all_caps_form(table):
    assert find_real_names("BRILLIANT", table) == ["BRILLIANT"]
    assert find_real_names("BRILLIANT_API_URL=x", table) == ["BRILLIANT"]
    assert mask_text("BRILLIANT_API_URL", table) == "BRILLO_API_URL"
    assert find_real_names("A BRILLIANT IDEA", table) == ["BRILLIANT"]


def test_case_sensitive_identifiers(table):
    assert find_real_names("brilliant_theme", table) == []
    assert find_real_names("BrilliantTheme", table) == ["Brilliant"]
    assert mask_text("BrilliantTheme", table) == "BrilloTheme"


def test_case_sensitive_all_caps_form_keeps_accent_insensitivity():
    table = NamesTable((Name("Méridia", "Meridiana", (), True),), ())
    assert find_real_names("MERIDIA MÉRIDIA", table) == ["MERIDIA", "MÉRIDIA"]
    assert find_real_names("méridia", table) == []


def test_case_sensitive_entry_masks_only_the_capitalized_word(table):
    assert mask_text("a brilliant idea by Brilliant", table) == "a brilliant idea by Brillo"


def test_alias_maps_to_analog(table):
    assert mask_text("ACME Corp", table) == "Apex"


def test_whitespace_inside_a_term_is_flexible(table):
    assert mask_text("Acme\n  Capital", table) == "Summit Partners"


def test_idempotent(table):
    text = "Acme Capital, ACME Corp, acme, Brilliant, brilliant, MÉRIDIA"
    once = mask_text(text, table)
    assert mask_text(once, table) == once


def test_text_without_names_is_unchanged(table):
    text = "nothing to hide here\n"
    assert mask_text(text, table) == text
    assert find_real_names(text, table) == []


def test_matches_come_back_in_order(table):
    assert find_real_names("Méridia, then Acme Capital, then acme", table) == [
        "Méridia",
        "Acme Capital",
        "acme",
    ]


def test_blocked_domain(table):
    assert find_blocked_domains("x.ACME-CORP.example/a", table) == ["ACME-CORP.example"]
    assert find_blocked_domains("example.org", table) == []


def test_empty_table_matches_nothing():
    empty = NamesTable((), ())
    assert find_real_names("Acme", empty) == []
    assert find_blocked_domains("acme-corp.example", empty) == []
    assert mask_text("Acme", empty) == "Acme"


def test_missing_table_raises(tmp_path):
    with pytest.raises(NamesTableMissing) as error:
        load_names(tmp_path / "absent.toml")
    assert error.value.path == tmp_path / "absent.toml"


def test_default_path_is_the_config_dir(ws_config):
    assert load_names().names[0].real == "Acme Capital"


def test_load_reads_every_field(table):
    acme = next(name for name in table.names if name.real == "Acme")
    assert acme == Name("Acme", "Apex", ("ACME Corp",), False)
    brilliant = next(name for name in table.names if name.real == "Brilliant")
    assert brilliant.case_sensitive is True
    assert table.blocked_domains == ("acme-corp.example",)


@pytest.mark.parametrize(
    "content",
    [
        '[[names]]\nanalog = "Apex"\n',
        '[[names]]\nreal = ""\nanalog = "Apex"\n',
        '[[names]]\nreal = "Acme"\nanalog = "Apex"\naliases = [""]\n',
        '[[names]]\nreal = "Acme"\nanalog = "Apex"\ncase_sensitive = "yes"\n',
        'blocked_domains = [""]\n',
    ],
)
def test_invalid_table_is_rejected(tmp_path, content):
    path = tmp_path / "names.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_names(path)
