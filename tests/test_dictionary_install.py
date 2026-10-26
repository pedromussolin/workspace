"""Installing the dictionaries without root, with fake `apt-get` and `dpkg`: no network."""

import pytest

from ws import config, dictionary


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """A fresh, empty data dir and cache dir, and no system dictionaries."""
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WS_SYSTEM_DICT_DIR", str(tmp_path / "no-system-dict"))
    return tmp_path


def leftovers(folder):
    return sorted(path.name for path in folder.iterdir()) if folder.exists() else []


def test_install_puts_both_dictionaries_in_the_data_dir(dirs, fake_apt):
    assert [source.package for source in dictionary.missing()] == ["wamerican", "wbrazilian"]

    installed = dictionary.install()

    assert installed == [
        dirs / "data" / "dict" / "american-english",
        dirs / "data" / "dict" / "brazilian",
    ]
    assert dictionary.missing() == []
    assert dictionary.load() == {"flange", "gizmo", "porca", "arruela"}


def test_install_downloads_and_unpacks_without_root_inside_the_cache_dir(dirs, fake_apt):
    dictionary.install()

    apt, first, second = fake_apt.calls()
    cache = config.cache_dir()
    assert apt["tool"] == "apt-get"
    assert apt["args"] == ["download", "wamerican", "wbrazilian"]
    for call in (apt, first, second):
        assert call["cwd"].startswith(str(cache)), "work happens in the cache dir, never /tmp"
    assert [(call["tool"], call["args"][0]) for call in (first, second)] == [
        ("dpkg", "-x"),
        ("dpkg", "-x"),
    ]
    assert first["args"][1].endswith("wamerican_1.0_all.deb")
    assert second["args"][1].endswith("wbrazilian_1.0_all.deb")
    assert first["args"][2] != second["args"][2], "each package unpacks in its own folder"
    assert all(call["tool"] in {"apt-get", "dpkg"} for call in fake_apt.calls())


def test_install_removes_its_work_folder(dirs, fake_apt):
    dictionary.install()
    assert leftovers(dirs / "cache") == []
    assert leftovers(dirs / "data" / "dict") == ["american-english", "brazilian"]


def test_install_replaces_what_the_data_dir_has(dirs, fake_apt):
    folder = dirs / "data" / "dict"
    folder.mkdir(parents=True)
    (folder / "brazilian").write_text("velho\n", encoding="utf-8")
    dictionary.install()
    assert (folder / "brazilian").read_text(encoding="utf-8") == "porca\narruela\n"


def test_a_failed_download_is_reported_with_the_last_line_of_apt(dirs, fake_apt, monkeypatch):
    monkeypatch.setenv("FAKE_APT_FAIL", "1")
    with pytest.raises(dictionary.InstallError) as error:
        dictionary.install()
    assert str(error.value) == "apt-get download failed: E: Unable to locate package wamerican"
    assert [call["tool"] for call in fake_apt.calls()] == ["apt-get"]
    assert leftovers(dirs / "cache") == []
    assert not (dirs / "data").exists()


def test_a_failed_unpack_is_reported_and_leaves_nothing(dirs, fake_apt, monkeypatch):
    monkeypatch.setenv("FAKE_DPKG_FAIL", "1")
    with pytest.raises(dictionary.InstallError, match="dpkg -x failed: dpkg-deb: error"):
        dictionary.install()
    assert leftovers(dirs / "cache") == []
    assert not (dirs / "data").exists()


@pytest.mark.parametrize("tool", ["apt-get", "dpkg"])
def test_a_missing_tool_is_reported_before_anything_runs(dirs, fake_apt, monkeypatch, tool):
    (fake_apt.folder / tool).unlink()
    only_one = dirs / "bin"
    only_one.mkdir()
    other = "dpkg" if tool == "apt-get" else "apt-get"
    (only_one / other).symlink_to(fake_apt.folder / other)
    monkeypatch.setenv("PATH", str(only_one))
    with pytest.raises(dictionary.InstallError, match="apt-get or dpkg was not found"):
        dictionary.install()
    assert fake_apt.calls() == []
    assert not (dirs / "cache").exists()


def test_a_package_without_its_dictionary_installs_nothing(dirs, fake_apt, monkeypatch):
    monkeypatch.setenv("FAKE_DPKG_MODE", "empty")
    with pytest.raises(dictionary.InstallError, match="american-english is missing or empty"):
        dictionary.install()
    assert leftovers(dirs / "cache") == []
    assert not (dirs / "data").exists()


def test_a_dictionary_that_is_a_link_is_refused(dirs, fake_apt, monkeypatch):
    outside = dirs / "elsewhere.txt"
    outside.write_text("not a dictionary\n", encoding="utf-8")
    monkeypatch.setenv("FAKE_DPKG_MODE", "symlink")
    monkeypatch.setenv("FAKE_DPKG_LINK", str(outside))
    with pytest.raises(dictionary.InstallError, match="missing or empty"):
        dictionary.install()
    assert not (dirs / "data").exists()


def test_the_first_dictionary_is_not_installed_when_the_second_is_bad(
    dirs, fake_apt, monkeypatch, tmp_path
):
    script = fake_apt.folder / "dpkg"
    text = script.read_text(encoding="utf-8").replace(
        'if mode == "empty":', 'if mode == "empty" and deb.name.startswith("wbrazilian"):'
    )
    script.write_text(text, encoding="utf-8")
    monkeypatch.setenv("FAKE_DPKG_MODE", "empty")
    with pytest.raises(dictionary.InstallError, match="brazilian is missing or empty"):
        dictionary.install()
    assert not (dirs / "data").exists()
