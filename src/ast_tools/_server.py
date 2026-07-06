#!/usr/bin/env python3
"""
AST Tools MCP Server — structural code analysis and editing tools.

Exposes 60+ MCP tools for structural code analysis, semantic search,
dependency analysis, and code modification.

Supports three server modes:
    timeout (default): stdio transport with configurable idle timeout
    daemon:          Persistent Unix socket daemon via systemd
    remote:          Streamable HTTP server with optional bearer auth

Mode selection (in priority order):
    1. --mode CLI flag
    2. AST_TOOLS_MODE env var
    3. Config file setting
    4. Default: timeout
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import signal
import sys
import time
from typing import Any

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ast_tools.server_config import add_server_args, config_from_args
from ast_tools.tools import TOOL_REGISTRY, get_tool_handler, list_tool_names

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger(__name__)

server = Server("rw-ast-tools")


# ─── Tool Definitions ────────────────────────────────────────────────────


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Dynamically build Tool definitions from TOOL_SCHEMAS."""
    from ast_tools.tools import TOOL_SCHEMAS, list_tool_names

    tools: list[Tool] = []
    names = list_tool_names()
    for name in sorted(names):
        schema = TOOL_SCHEMAS.get(name)
        if schema is None:
            continue
        tools.append(
            Tool(
                name=name,
                description=schema.get("description", ""),
                inputSchema=schema.get("inputSchema", {"type": "object", "properties": {}}),
            )
        )
    return tools


# ─── Tool Handlers ────────────────────────────────────────────────────────


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to registered handlers."""
    try:
        if name not in TOOL_REGISTRY:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Unknown tool: {name}",
                        "error_code": "NOT_FOUND",
                        "available_tools": list_tool_names(),
                    }),
                )
            ]

        handler = get_tool_handler(name)
        result = await anyio.to_thread.run_sync(handler, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": str(e), "error_code": "INTERNAL", "tool": name}),
            )
        ]


# ─── Mode: Timeout (stdio with idle TTL) ─────────────────────────────────


async def _run_timeout_mode(config: dict[str, Any]) -> None:
    """Run server in timeout mode — stdio with idle shutdown."""
    timeout_seconds = config["server"]["timeout_seconds"]
    last_activity = time.monotonic()

    def _update_activity():
        nonlocal last_activity
        last_activity = time.monotonic()

    # Wrap tool call handler to track activity
    original_handler = server.call_tool

    @server.call_tool()
    async def _timed_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        _update_activity()
        return await original_handler(name, arguments)

    async with stdio_server() as (read_stream, write_stream):
        # Start idle timeout monitor
        async with anyio.create_task_group() as tg:
            tg.start_soon(_idle_monitor, timeout_seconds, _update_activity)
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )


async def _idle_monitor(timeout_seconds: int, get_last_activity) -> None:
    """Monitor idle time and shutdown when exceeded."""
    while True:
        await anyio.sleep(timeout_seconds)
        if time.monotonic() - get_last_activity() >= timeout_seconds:
            logger.info("Idle timeout reached (%ds) — shutting down", timeout_seconds)
            # Trigger graceful shutdown
            os.kill(os.getpid(), signal.SIGTERM)
            break


# ─── Mode: Daemon (Unix socket) ─────────────────────────────────────────


async def _run_daemon_mode(config: dict[str, Any]) -> None:
    """Run server in daemon mode — persistent stdio with watchdog."""
    socket_path = config["daemon"]["socket_path"]
    logger.info("Starting daemon mode (socket: %s)", socket_path)

    # Start watchdog in background
    from ast_tools.watchdog.monitor import CodebaseWatcher
    watcher = CodebaseWatcher(config)
    if watcher.enabled:
        try:
            cwd = os.getcwd()
            msg = watcher.start(cwd)
            logger.info("Watchdog: %s", msg)
        except Exception as e:
            logger.warning("Watchdog failed to start: %s", e)

    # Run stdio server persistently (systemd manages lifecycle)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


# ─── Mode: Remote (Streamable HTTP) ──────────────────────────────────────

async def _run_remote_mode(config: dict[str, Any]) -> None:
    """Run server in remote mode — Streamable HTTP.

    Uses MCP v2 streamable HTTP transport via StreamableHTTPSessionManager.
    Auth is handled at the reverse proxy layer.
    """
    host = config["remote"]["host"]
    port = config["remote"]["port"]

    logger.info("Starting remote mode on %s:%s", host, port)

    try:
        from contextlib import asynccontextmanager

        import uvicorn
        from mcp.server.fastmcp.server import StreamableHTTPASGIApp
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        from starlette.applications import Starlette
        from starlette.routing import Route

        # Create session manager with the low-level Server
        session_manager = StreamableHTTPSessionManager(
            app=server,
            json_response=True,
            stateless=True,
        )

        # Create the ASGI handler
        asgi_app = StreamableHTTPASGIApp(session_manager)

        # Wrap in Starlette with lifespan to run the session manager
        @asynccontextmanager
        async def lifespan(app):
            async with session_manager.run():
                yield

        starlette_app = Starlette(
            routes=[Route("/mcp", asgi_app)],
            lifespan=lifespan,
        )

        config_uv = uvicorn.Config(
            starlette_app,
            host=host,
            port=port,
            log_level="warning",
        )
        uv_server = uvicorn.Server(config_uv)
        try:
            await uv_server.serve()
        except SystemExit as e:
            if e.code != 0:
                raise RuntimeError(f"Uvicorn exited with code {e.code}") from e
    except ImportError as e:
        logger.error("Remote mode requires mcp SDK with streamable HTTP: %s", e)
        await _run_legacy_http(host, port, "")
    except RuntimeError:
        # Port conflict or other startup failure — propagate, don't fall back
        raise


async def _run_legacy_http(host: str, port: int, auth_token: str) -> None:
    """Fallback HTTP server when MCP v2 streamable_http is unavailable."""
    import asyncio

    from aiohttp import web

    async def handle_mcp(request):
        if auth_token:
            provided = request.headers.get("Authorization", "")
            if provided != f"Bearer {auth_token}":
                return web.json_response({"error": "Unauthorized"}, status=401)

        body = await request.json()
        method = body.get("method", "")

        if method == "initialize":
            return web.json_response({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "rw-ast-tools", "version": "0.1.0"},
                },
            })
        elif method == "tools/list":
            tools = await list_tools()
            return web.json_response({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {"tools": [{
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema,
                } for t in tools]},
            })
        elif method == "tools/call":
            params = body.get("params", {})
            result = await call_tool(
                params.get("name", ""),
                params.get("arguments", {}),
            )
            return web.json_response({
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": {"content": [r.model_dump() for r in result]},
            })
        else:
            return web.json_response(
                {"jsonrpc": "2.0", "id": body.get("id", 0),
                 "error": {"code": -32601, "message": "Method not found"}},
                status=404,
            )

    app = web.Application()
    app.router.add_post("/mcp", handle_mcp)
    app.router.add_get("/health", lambda r: web.json_response({"status": "ok"}))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("Legacy HTTP server listening on %s:%s", host, port)

    # Keep running
    await asyncio.Event().wait()


# ─── Entry point ─────────────────────────────────────────────────────────


async def main():
    """Run the ast-tools MCP server in the configured mode."""
    import argparse

    parser = argparse.ArgumentParser(description="rw-ast-tools MCP Server")
    add_server_args(parser)
    parser.add_argument("--foreground", action="store_true",
                        help="Keep process in foreground (for systemd)")
    args = parser.parse_args()
    config = config_from_args(args)

    mode = config["server"]["mode"]
    logger.info("Starting rw-ast-tools server in %s mode", mode)

    if mode == "timeout":
        await _run_timeout_mode(config)
    elif mode == "daemon":
        await _run_daemon_mode(config)
    elif mode == "remote":
        await _run_remote_mode(config)
    else:
        logger.error("Unknown mode: %s — falling back to timeout", mode)
        await _run_timeout_mode(config)


def main_sync():
    """Synchronous entry point for console_scripts."""
    import anyio
    with contextlib.suppress(KeyboardInterrupt):
        anyio.run(main)


if __name__ == "__main__":
    main_sync()
