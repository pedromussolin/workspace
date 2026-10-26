from ws import config


def test_config_dir_respects_env(monkeypatch, tmp_path):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))
    assert config.config_dir() == tmp_path


def test_config_dir_default(monkeypatch):
    monkeypatch.delenv("WS_CONFIG_DIR", raising=False)
    assert config.config_dir().parts[-2:] == (".config", "workspace")
