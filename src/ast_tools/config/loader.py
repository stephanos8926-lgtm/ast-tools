"""Config directory resolver with env override, XDG compliance, and legacy migration."""

import os
import shutil
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Raised on config-related errors."""


_AST_TOOLS_HOME = "AST_TOOLS_HOME"


def _validate_safe_path(path: Path) -> None:
    """Reject paths with traversal, symlink escape, or non-absolute."""
    path.resolve()
    if ".." in str(path):
        raise ConfigError(f"Path contains '..': {path}")
    if not path.is_absolute():
        raise ConfigError(f"Path must be absolute: {path}")


def get_config_dir() -> Path:
    """Resolve config directory (env override > XDG > ~/.ast-tools)."""
    if env_home := os.environ.get(_AST_TOOLS_HOME):
        path = Path(env_home).resolve()
        _validate_safe_path(path)
        return path
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "ast-tools"
    return Path.home() / ".ast-tools"


def get_cache_dir() -> Path:
    """Return cache directory (XDG_CACHE_HOME or under config dir)."""
    if env_home := os.environ.get(_AST_TOOLS_HOME):
        return Path(env_home) / "cache"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "ast-tools"
    return get_config_dir() / "cache"


def get_data_dir() -> Path:
    """Return data directory (XDG_DATA_HOME or under config dir)."""
    if env_home := os.environ.get(_AST_TOOLS_HOME):
        return Path(env_home) / "data"
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "ast-tools"
    return get_config_dir() / "data"


def ensure_config_dir(config_dir: Path | None = None) -> Path:
    """Create config directory structure idempotently."""
    cfg = config_dir or get_config_dir()
    cfg = cfg.resolve()
    for subdir in ["config", "cache/models", "cache/tmp", "logs", "backups"]:
        (cfg / subdir).mkdir(parents=True, exist_ok=True)
    return cfg


def migrate_legacy() -> bool:
    """Migrate data from ~/.cache/ast-tools/ to new config dir."""
    legacy = Path.home() / ".cache" / "ast-tools"
    if not legacy.exists():
        return False

    target = get_data_dir()
    legacy_db = legacy / "codebase.db"
    if legacy_db.exists():
        target_db = target / "codebase.db"
        if not target_db.exists():
            target_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_db, target_db)

    legacy_models = legacy / "models"
    if legacy_models.exists():
        target_models = target / "models"
        if not target_models.exists():
            shutil.copytree(legacy_models, target_models)

    return True


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base with type safety."""
    result = base.copy()
    for key, val in override.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = _deep_merge(result[key], val)
            elif type(result[key]) is not type(val):
                raise ConfigError(
                    f"Type mismatch for '{key}': "
                    f"expected {type(result[key]).__name__}, got {type(val).__name__}"
                )
            else:
                result[key] = val
        else:
            result[key] = val
    return result


def load_config(name: str = "tokens") -> dict:
    """Load a YAML config file from the config directory."""
    config_dir = get_config_dir()
    config_path = config_dir / "config" / f"{name}.yaml"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def load_tokens_config() -> dict:
    """Load tokens.yaml and merge with defaults."""
    from .tokens_schema import DEFAULT_TOKENS

    raw = load_config("tokens")
    if not raw:
        return dict(DEFAULT_TOKENS)
    try:
        return _deep_merge(DEFAULT_TOKENS, raw)
    except ConfigError:
        return dict(DEFAULT_TOKENS)


def write_config(path: Path, data: dict) -> None:
    """Write config atomically (tmp + rename)."""
    path = path.resolve()
    tmp_path = path.with_suffix(".tmp")
    try:
        tmp_path.write_text(yaml.dump(data, default_flow_style=False))
        tmp_path.chmod(0o600)
        tmp_path.rename(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
