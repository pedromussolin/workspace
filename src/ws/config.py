"""Paths used by ws. Each one can be overridden by an environment variable, which the tests use."""

import os
import re
import shutil
from pathlib import Path

REPO_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


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


def claude_user_instructions_path() -> Path:
    return _env_path("WS_CLAUDE_USER_INSTRUCTIONS", Path.home() / ".claude" / "CLAUDE.md")


def claude_settings_path() -> Path:
    return _env_path("WS_CLAUDE_SETTINGS", Path.home() / ".claude" / "settings.json")


def claude_json_path() -> Path:
    return _env_path("WS_CLAUDE_JSON", Path.home() / ".claude.json")


def claude_plugins_dir() -> Path:
    return _env_path("WS_CLAUDE_PLUGINS_DIR", Path.home() / ".claude" / "plugins")


def ws_executable() -> Path | None:
    """The absolute path of `ws`, for a command Claude Code runs without the shell PATH."""
    override = os.environ.get("WS_BIN")
    if override:
        return Path(override).absolute()
    found = shutil.which("ws")
    if found:
        return Path(found).absolute()
    local = Path.home() / ".local" / "bin" / "ws"
    return local if local.exists() else None


def claude_hooks_dir() -> Path:
    return _env_path("WS_CLAUDE_HOOKS_DIR", Path.home() / ".claude" / "hooks" / "workspace")


def repo_root() -> Path:
    return _env_path("WS_REPO_ROOT", Path(__file__).resolve().parents[2])
