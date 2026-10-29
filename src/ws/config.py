"""Paths used by ws. Each one can be overridden by an environment variable, which the tests use."""

import os
from pathlib import Path


def _env_path(var: str, default: Path) -> Path:
    value = os.environ.get(var)
    return Path(value) if value else default


def config_dir() -> Path:
    return _env_path("WS_CONFIG_DIR", Path.home() / ".config" / "workspace")


def cache_dir() -> Path:
    return _env_path("WS_CACHE_DIR", Path.home() / ".cache" / "workspace")


def data_dir() -> Path:
    return _env_path("WS_DATA_DIR", Path.home() / ".local" / "share" / "workspace")


def system_dict_dir() -> Path:
    return _env_path("WS_SYSTEM_DICT_DIR", Path("/usr/share/dict"))


def claude_skills_dir() -> Path:
    return _env_path("WS_CLAUDE_SKILLS_DIR", Path.home() / ".claude" / "skills")


def claude_settings_path() -> Path:
    return _env_path("WS_CLAUDE_SETTINGS", Path.home() / ".claude" / "settings.json")


def claude_hooks_dir() -> Path:
    return _env_path("WS_CLAUDE_HOOKS_DIR", Path.home() / ".claude" / "hooks" / "workspace")


def repo_root() -> Path:
    return _env_path("WS_REPO_ROOT", Path(__file__).resolve().parents[2])
