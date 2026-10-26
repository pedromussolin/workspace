"""The common-word dictionaries: where they are read from and which entries count."""

from ws import config, dictionary


def test_data_dir_respects_env_and_defaults_to_the_local_share(monkeypatch, tmp_path):
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path))
    assert config.data_dir() == tmp_path
    monkeypatch.delenv("WS_DATA_DIR")
    assert config.data_dir().parts[-3:] == (".local", "share", "workspace")


def test_system_dict_dir_respects_env_and_defaults_to_usr_share_dict(monkeypatch, tmp_path):
    monkeypatch.setenv("WS_SYSTEM_DICT_DIR", str(tmp_path))
    assert config.system_dict_dir() == tmp_path
    monkeypatch.delenv("WS_SYSTEM_DICT_DIR")
    assert str(config.system_dict_dir()) == "/usr/share/dict"


def test_the_data_dir_wins_over_the_system_dir(ws_dictionaries, monkeypatch, tmp_path):
    system = tmp_path / "system"
    system.mkdir()
    (system / "american-english").write_text("system\n", encoding="utf-8")
    (system / "brazilian").write_text("sistema\n", encoding="utf-8")
    monkeypatch.setenv("WS_SYSTEM_DICT_DIR", str(system))
    assert dictionary.load() == {"gadget", "sprocket", "engrenagem", "parafuso"}
    (ws_dictionaries / "american-english").unlink()
    assert dictionary.load() == {"system", "engrenagem", "parafuso"}


def test_each_file_is_found_on_its_own(ws_dictionaries, monkeypatch, tmp_path):
    system = tmp_path / "system"
    system.mkdir()
    (system / "brazilian").write_text("sistema\n", encoding="utf-8")
    (ws_dictionaries / "brazilian").unlink()
    monkeypatch.setenv("WS_SYSTEM_DICT_DIR", str(system))
    assert dictionary.missing() == []
    assert dictionary.load() == {"gadget", "sprocket", "sistema"}


def test_missing_names_the_packages_without_a_file(ws_dictionaries):
    assert dictionary.missing() == []
    (ws_dictionaries / "brazilian").unlink()
    assert [source.package for source in dictionary.missing()] == ["wbrazilian"]
    (ws_dictionaries / "american-english").unlink()
    assert [source.package for source in dictionary.missing()] == ["wamerican", "wbrazilian"]
    assert dictionary.load() == frozenset()


def test_only_lowercase_entries_of_letters_count_and_they_are_folded(ws_dictionaries):
    entries = "Zorblax\nbanana\nd'agua\nre-fazer\nAçúcar\nação\nCAFÉ\n\n  parafuso  \niPhone\n"
    (ws_dictionaries / "brazilian").write_text(entries, encoding="utf-8")
    (ws_dictionaries / "american-english").write_text("don't\nplain\n", encoding="utf-8")
    assert dictionary.load() == {"banana", "acao", "parafuso", "iphone", "plain"}


def test_a_byte_that_is_not_utf_8_does_not_stop_the_load(ws_dictionaries):
    (ws_dictionaries / "brazilian").write_bytes(b"banana\ncoca\xe7\xe3o\nparafuso\n")
    assert {"banana", "parafuso"} <= dictionary.load()
