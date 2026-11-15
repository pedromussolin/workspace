import pytest

from ws.observability import open_observability, providers
from ws.observability.port import Observability, Setup


def write_config(tmp_path, monkeypatch, text):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))
    if text is not None:
        (tmp_path / "config.toml").write_text(text)


def test_open_observability_by_provider(tmp_path, monkeypatch):
    write_config(tmp_path, monkeypatch, '[observability]\nprovider = "datadog"\n')
    found = open_observability()
    assert isinstance(found, Observability)
    assert found.tool == "execute_code"
    assert providers() == ("datadog",)


@pytest.mark.parametrize("text", [None, "[other]\nx = 1\n", "[observability]\n"])
def test_open_observability_without_provider(tmp_path, monkeypatch, text):
    write_config(tmp_path, monkeypatch, text)
    with pytest.raises(Setup, match=r"\[observability\] provider"):
        open_observability()


def test_open_observability_unknown_provider(tmp_path, monkeypatch):
    write_config(tmp_path, monkeypatch, '[observability]\nprovider = "nope"\n')
    with pytest.raises(Setup, match="datadog"):
        open_observability()
