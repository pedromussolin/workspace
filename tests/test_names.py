import stat

import pytest

from ws.names import (
    Name,
    NamesTable,
    NamesTableMissing,
    add_name,
    find_blocked_domains,
    find_real_names,
    fold,
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


def test_fold_ignores_case_and_accents():
    assert fold("Méridia") == fold("MERIDIA") == "meridia"
    assert fold("Straße") == "strasse"
    assert fold("Ação") == "acao"
    assert fold("Me\u0301ridia") == "meridia"


def test_add_name_appends_and_keeps_the_content_and_the_mode(names_toml):
    names_toml.chmod(0o600)
    before = names_toml.read_text(encoding="utf-8")
    add_name(names_toml, " Zorblax ", "Zeta", case_sensitive=True)
    text = names_toml.read_text(encoding="utf-8")
    assert text.startswith(before)
    assert text.endswith('\n[[names]]\nreal = "Zorblax"\nanalog = "Zeta"\ncase_sensitive = true\n')
    assert stat.S_IMODE(names_toml.stat().st_mode) == 0o600
    assert load_names(names_toml).names[-1] == Name("Zorblax", "Zeta", (), True)


def test_add_name_refuses_what_the_table_has_and_changes_nothing(names_toml):
    before = names_toml.read_text(encoding="utf-8")
    for real, analog in [("ACME CORP", "x"), ("méridia", "x"), ("Summit Partners", "x"), ("", "x")]:
        with pytest.raises(ValueError):
            add_name(names_toml, real, analog)
    with pytest.raises(ValueError, match="must differ"):
        add_name(names_toml, "Zorblax", "ZORBLAX")
    assert names_toml.read_text(encoding="utf-8") == before


def test_add_name_does_not_create_the_table(tmp_path):
    with pytest.raises(NamesTableMissing):
        add_name(tmp_path / "names.toml", "Zorblax", "Zeta")
    assert list(tmp_path.iterdir()) == []
