import pytest

from ws.observability import open_observability, providers
from ws.observability.port import Observability, Setup


def write_config(tmp_path, monkeypatch, text):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))
    if text is not None:
        (tmp_path / "config.toml").write_text(text)


def test_providers_are_the_adapter_modules():
    assert providers() == tuple(sorted(providers()))
    assert providers()


def test_open_observability_by_provider(tmp_path, monkeypatch):
    name = providers()[0]
    write_config(tmp_path, monkeypatch, f'[observability]\nprovider = "{name}"\n')
    found = open_observability()
    assert isinstance(found, Observability)
    assert found.kind == name


@pytest.mark.parametrize("text", [None, "[other]\nx = 1\n", "[observability]\n"])
def test_open_observability_without_provider(tmp_path, monkeypatch, text):
    write_config(tmp_path, monkeypatch, text)
    with pytest.raises(Setup, match=r"\[observability\] provider"):
        open_observability()


def test_open_observability_unknown_provider(tmp_path, monkeypatch):
    write_config(tmp_path, monkeypatch, '[observability]\nprovider = "nope"\n')
    with pytest.raises(Setup, match=providers()[0]):
        open_observability()
