"""Tests for ast_tools.server_config module."""

import os

from ast_tools.server_config import DEFAULT_CONFIG, load_server_config


class TestLoadServerConfig:
    def test_default_config(self):
        cfg = load_server_config()
        assert cfg["server"]["mode"] == "timeout"
        assert cfg["server"]["timeout_seconds"] == 900

    def test_cli_mode_override(self):
        cfg = load_server_config(cli_mode="daemon")
        assert cfg["server"]["mode"] == "daemon"

    def test_cli_port_override(self):
        cfg = load_server_config(cli_port=9999)
        assert cfg["remote"]["port"] == 9999

    def test_cli_timeout_override(self):
        cfg = load_server_config(cli_timeout=60)
        assert cfg["server"]["timeout_seconds"] == 60

    def test_env_var_override(self):
        os.environ["AST_TOOLS_MODE"] = "remote"
        try:
            cfg = load_server_config()
            assert cfg["server"]["mode"] == "remote"
        finally:
            del os.environ["AST_TOOLS_MODE"]

    def test_env_var_bool_coercion(self):
        os.environ["AST_TOOLS_DAEMON_WATCHDOGS"] = "false"
        try:
            cfg = load_server_config()
            assert cfg["daemon"]["watchdogs"] is False
        finally:
            del os.environ["AST_TOOLS_DAEMON_WATCHDOGS"]

    def test_env_var_int_coercion(self):
        os.environ["AST_TOOLS_TIMEOUT"] = "120"
        try:
            cfg = load_server_config()
            assert cfg["server"]["timeout_seconds"] == 120
        finally:
            del os.environ["AST_TOOLS_TIMEOUT"]

    def test_cli_beats_env_var(self):
        os.environ["AST_TOOLS_MODE"] = "daemon"
        try:
            cfg = load_server_config(cli_mode="timeout")
            assert cfg["server"]["mode"] == "timeout"
        finally:
            del os.environ["AST_TOOLS_MODE"]

    def test_all_default_keys_present(self):
        cfg = load_server_config()
        for section, vals in DEFAULT_CONFIG.items():
            assert section in cfg, f"Missing section: {section}"
            for key in vals:
                assert key in cfg[section], f"Missing key: {section}.{key}"

    def test_invalid_env_var_ignored(self):
        os.environ["AST_TOOLS_TIMEOUT"] = "not-a-number"
        try:
            cfg = load_server_config()
            assert cfg["server"]["timeout_seconds"] == 900  # unchanged
        finally:
            del os.environ["AST_TOOLS_TIMEOUT"]
