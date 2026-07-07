"""Server configuration for rw-ast-tools server modes.

Three-tier config resolution: CLI flags > env vars > config file > defaults.
Named 'server_config' to avoid collision with existing ast_tools.config package.
"""

from __future__ import annotations

import contextlib
import copy
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    import argparse

# ── Type aliases ────────────────────────────────────────────────────────

ServerMode = Literal["timeout", "daemon", "remote"]

# ── Defaults ────────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict[str, Any] = {
    "server": {
        "mode": "timeout",
        "timeout_seconds": 900,
    },
    "daemon": {
        "socket_path": str(Path.home() / ".cache" / "rw-ast-tools" / "server.sock"),
        "watchdogs": True,
        "max_codebases": 10,
    },
    "remote": {
        "host": "127.0.0.1",
        "port": 8100,
        "auth_token": "",
        "tls_cert": "",
        "tls_key": "",
    },
    "watchdog": {
        "enabled": True,
        "debounce_ms": 100,
        "auto_index": True,
        "metrics_ttl_hours": 168,
    },
}

CONFIG_FILE_PATHS = [
    Path.home() / ".config" / "rw-ast-tools" / "config.yaml",
    Path.cwd() / ".ast-tools" / "config.yaml",
]

ENV_MAP: dict[str, tuple[str, ...]] = {
    "AST_TOOLS_MODE": ("server", "mode"),
    "AST_TOOLS_TIMEOUT": ("server", "timeout_seconds"),
    "AST_TOOLS_DAEMON_SOCKET": ("daemon", "socket_path"),
    "AST_TOOLS_DAEMON_WATCHDOGS": ("daemon", "watchdogs"),
    "AST_TOOLS_REMOTE_HOST": ("remote", "host"),
    "AST_TOOLS_REMOTE_PORT": ("remote", "port"),
    "AST_TOOLS_AUTH_TOKEN": ("remote", "auth_token"),
    "AST_TOOLS_TLS_CERT": ("remote", "tls_cert"),
    "AST_TOOLS_TLS_KEY": ("remote", "tls_key"),
    "AST_TOOLS_WATCHDOG_ENABLED": ("watchdog", "enabled"),
    "AST_TOOLS_WATCHDOG_DEBOUNCE": ("watchdog", "debounce_ms"),
}


def load_server_config(
    config_path: Path | None = None,
    cli_mode: str | None = None,
    cli_port: int | None = None,
    cli_host: str | None = None,
    cli_timeout: int | None = None,
    cli_auth_token: str | None = None,
) -> dict[str, Any]:
    """Load server configuration with three-tier resolution.

    Priority: CLI flags > env vars > config file > hardcoded defaults.
    """
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    loaded = _load_config_file(config_path)
    _merge_config(cfg, loaded)
    for var, keys in ENV_MAP.items():
        val = os.environ.get(var)
        if val is not None:
            _apply_env_value(cfg, keys, val)
    if cli_mode is not None:
        cfg["server"]["mode"] = cli_mode
    if cli_timeout is not None:
        cfg["server"]["timeout_seconds"] = cli_timeout
    if cli_host is not None:
        cfg["remote"]["host"] = cli_host
    if cli_port is not None:
        cfg["remote"]["port"] = cli_port
    if cli_auth_token is not None:
        cfg["remote"]["auth_token"] = cli_auth_token
    return cfg


def _load_config_file(explicit_path: Path | None) -> dict:
    paths = [explicit_path] if explicit_path else CONFIG_FILE_PATHS
    for path in paths:
        if path and path.exists():
            try:
                import yaml

                raw = yaml.safe_load(path.read_text())
                if isinstance(raw, dict):
                    return raw
            except Exception:
                import logging

                logging.getLogger(__name__).warning("Failed to load config from %s", path)
    return {}


def _merge_config(base: dict, overlay: dict) -> None:
    for key, val in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _merge_config(base[key], val)
        else:
            base[key] = val


def _apply_env_value(cfg: dict, keys: tuple[str, ...], raw: str) -> None:
    target = cfg
    for k in keys[:-1]:
        target = target.get(k, {})
    key = keys[-1]
    default_val = target.get(key)
    if isinstance(default_val, bool):
        target[key] = raw.lower() in ("1", "true", "yes")
    elif isinstance(default_val, int):
        with contextlib.suppress(ValueError):
            target[key] = int(raw)
    else:
        target[key] = raw


def add_server_args(parser: argparse.ArgumentParser) -> None:
    """Add server-mode arguments to an ArgumentParser."""
    parser.add_argument(
        "--mode",
        "-m",
        choices=["timeout", "daemon", "remote"],
        help="Server mode (default: timeout, overrides AST_TOOLS_MODE)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="HTTP port for remote mode (overrides AST_TOOLS_REMOTE_PORT)",
    )
    parser.add_argument(
        "--host",
        help="Bind host (overrides AST_TOOLS_REMOTE_HOST)",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        help="Idle timeout in seconds (overrides AST_TOOLS_TIMEOUT)",
    )
    parser.add_argument(
        "--auth-token",
        help="Bearer auth token (overrides AST_TOOLS_AUTH_TOKEN)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config file",
    )


def config_from_args(args: Any) -> dict[str, Any]:
    """Build a config dict from parsed CLI args."""
    return load_server_config(
        config_path=getattr(args, "config", None),
        cli_mode=getattr(args, "mode", None),
        cli_port=getattr(args, "port", None),
        cli_host=getattr(args, "host", None),
        cli_timeout=getattr(args, "timeout", None),
        cli_auth_token=getattr(args, "auth_token", None),
    )
