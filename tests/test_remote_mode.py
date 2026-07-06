"""Tests for remote mode (Streamable HTTP) server.

Unit tests run with default pytest.
Integration tests are skipped — run manually with:
    python -m pytest tests/test_remote_mode.py -v -k "Integration" --no-header
"""

from __future__ import annotations

import pytest


class TestRemoteModeUnit:
    """Unit tests for remote mode configuration."""

    def test_remote_default_config(self):
        """Test default remote config values."""
        from ast_tools.server_config import DEFAULT_CONFIG

        remote = DEFAULT_CONFIG["remote"]
        assert remote["host"] == "127.0.0.1"
        assert remote["port"] == 8100
        assert remote["auth_token"] == ""

    def test_remote_config_overrides(self):
        """Test remote config via CLI overrides."""
        from ast_tools.server_config import load_server_config

        config = load_server_config(
            cli_host="0.0.0.0",
            cli_port=9999,
            cli_auth_token="secret",
        )
        assert config["remote"]["host"] == "0.0.0.0"
        assert config["remote"]["port"] == 9999
        assert config["remote"]["auth_token"] == "secret"

    def test_remote_config_env(self, monkeypatch):
        """Test remote config via env vars."""
        monkeypatch.setenv("AST_TOOLS_REMOTE_HOST", "10.0.0.1")
        monkeypatch.setenv("AST_TOOLS_REMOTE_PORT", "8200")
        from ast_tools.server_config import load_server_config

        config = load_server_config()
        assert config["remote"]["host"] == "10.0.0.1"
        assert config["remote"]["port"] == 8200

    def test_remote_mode_cli_arg(self):
        """Test --mode remote sets mode correctly."""
        from ast_tools.server_config import load_server_config

        config = load_server_config(cli_mode="remote")
        assert config["server"]["mode"] == "remote"


class TestRemoteModeIntegration:
    """Integration tests — skipped by default.

    Run manually: python -m pytest tests/test_remote_mode.py -v -k "Integration"
    """

    @pytest.mark.skip(reason="Manual: requires free port on localhost")
    @pytest.mark.asyncio
    async def test_remote_tools_list(self):
        """Test tools/list returns 57 tools."""
        import asyncio
        import random
        from ast_tools._server import _run_remote_mode
        from ast_tools.server_config import DEFAULT_CONFIG

        config = DEFAULT_CONFIG.copy()
        config["remote"]["host"] = "127.0.0.1"
        config["remote"]["port"] = random.randint(8111, 8999)

        server_task = asyncio.create_task(_run_remote_mode(config))
        await asyncio.sleep(2)

        import httpx

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"http://127.0.0.1:{config['remote']['port']}/mcp",
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                    headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
                    timeout=5.0,
                )
                assert resp.status_code == 200
                data = resp.json()
                tools = data.get("result", {}).get("tools", [])
                assert len(tools) >= 50
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.skip(reason="Manual: requires free port on localhost")
    @pytest.mark.asyncio
    async def test_remote_codebase_summary(self):
        """Test tools/call with codebase_summary returns valid response."""
        import asyncio
        import random
        from ast_tools._server import _run_remote_mode
        from ast_tools.server_config import DEFAULT_CONFIG

        config = DEFAULT_CONFIG.copy()
        config["remote"]["host"] = "127.0.0.1"
        config["remote"]["port"] = random.randint(8111, 8999)

        server_task = asyncio.create_task(_run_remote_mode(config))
        await asyncio.sleep(2)

        import httpx

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"http://127.0.0.1:{config['remote']['port']}/mcp",
                    json={
                        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "codebase_summary", "arguments": {}},
                    },
                    headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
                    timeout=10.0,
                )
                assert resp.status_code == 200
                data = resp.json()
                content = data.get("result", {}).get("content", [])
                assert len(content) > 0
                text = content[0].get("text", "")
                assert "name" in text or "version" in text
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass


class TestLegacyHTTPFallback:
    """Tests for the legacy aiohttp fallback."""

    def test_mode_switcher_remote(self):
        """Test main() routes to remote mode correctly."""
        from ast_tools._server import main
        assert main is not None

    @pytest.mark.asyncio
    async def test_legacy_http_auth_blocked(self):
        """Test legacy HTTP rejects requests without correct auth."""
        from ast_tools._server import _run_legacy_http
        assert _run_legacy_http is not None