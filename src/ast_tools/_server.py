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
from mcp.types import InitializedNotification, TextContent, Tool

from ast_tools.server_config import add_server_args, config_from_args
from ast_tools.tools import (
    TOOL_REGISTRY,
    get_tool_handler,
    list_tool_names,
    list_tools,
)

# Global activity tracking for idle timeout
# Global activity tracking for idle timeout
_last_activity = time.monotonic()

# Set up file logging to capture Forge interactions
log_file = "/tmp/ast-tools-forge.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Server started, logging to {log_file}")

def _update_activity() -> None:
    """Update the last activity timestamp for idle timeout."""
    global _last_activity
    _last_activity = time.monotonic()


def _get_last_activity():
    return _last_activity

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
logger = logging.getLogger(__name__)

server = Server("rw-ast-tools")

# Log all incoming requests
async def _log_request(request):
    logger.debug(f"Incoming request: {request.method}")
    return None  # Continue to next handler

server.request_handlers["*"] = _log_request


# ─── Notification Handlers ───────────────────────────────────────────────────


async def _handle_initialized(notification: InitializedNotification) -> None:
    """Handle the initialized notification from client."""
    logger.info("Client initialized")


server.notification_handlers[InitializedNotification] = _handle_initialized


# ─── Tool Handlers ────────────────────────────────────────────────────────


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Return list of all available tools.

    In discovery mode (AST_TOOLS_DISCOVERY_MODE=true), only meta-tools
    (search_tools, call_tool, tool_info, tool_usage_stats) are exposed.
    Individual tools are still callable through call_tool.
    """
    all_tools = list_tools()
    if os.environ.get("AST_TOOLS_DISCOVERY_MODE", "").lower() in ("true", "1", "yes"):
        meta_tools = {"search_tools", "call_tool", "tool_info", "tool_usage_stats"}
        return [t for t in all_tools if t.name in meta_tools]
    return all_tools


@server.list_resources()
async def handle_list_resources() -> list:
    """Return list of available resources (none for this server)."""
    return []


@server.list_prompts()
@server.list_prompts()
async def handle_list_prompts() -> list:
    """Return list of available prompts (none for this server)."""
    return []


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to registered handlers.

    MCP framework calls this with (tool_name, arguments) directly.
    """
    try:
        _update_activity()

        if name not in TOOL_REGISTRY:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": f"Unknown tool: {name}",
                            "error_code": "NOT_FOUND",
                            "available_tools": list_tool_names(),
                        }
                    ),
                )
            ]

        handler = get_tool_handler(name)
        # Our handlers expect (name, params) - pass both
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

    async with (
        stdio_server() as (read_stream, write_stream),
        anyio.create_task_group() as tg,
    ):
        # Start idle timeout monitor
        tg.start_soon(_idle_monitor, timeout_seconds, _get_last_activity)
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
    """Run server in daemon mode — persistent Unix socket with watchdog.

    Listens on a Unix domain socket (NDJSON framing), accepts MCP JSON-RPC
    from multiple clients simultaneously, and maintains the index hot across
    sessions. systemd manages the process lifecycle.
    """
    import asyncio as asyncio_mod
    import socket

    socket_path = os.path.expanduser(config["daemon"]["socket_path"])
    logger.info("Starting daemon mode (socket: %s)", socket_path)

    # Clean up stale socket from previous run
    if os.path.exists(socket_path):
        os.unlink(socket_path)

    # Create Unix socket FIRST (before watchdog — watchdog scan can block)
    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.bind(socket_path)
    server_sock.listen(5)
    os.chmod(socket_path, 0o600)  # Owner-only access

    logger.info("Daemon listening on %s", socket_path)

    # Start watchdog AFTER socket is live (watchdog scan can block)
    from ast_tools.watchdog.monitor import CodebaseWatcher

    watcher = CodebaseWatcher(config)
    if watcher.enabled:
        try:
            watch_paths = config["daemon"].get("watch_paths", [])
            if not watch_paths:
                watch_paths = [os.getcwd()]
                logger.info("No watch_paths configured, using CWD: %s", watch_paths[0])
            for path in watch_paths:
                msg = watcher.start(path)
                logger.info("Watchdog: %s", msg)
        except Exception as e:
            logger.warning("Watchdog failed to start: %s", e)

    async def handle_client(reader, writer):
        """Handle one MCP client connection over the socket."""
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                request = json.loads(line.decode("utf-8").strip())
                method = request.get("method")
                req_id = request.get("id")

                if method == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {"tools": {"listChanged": False}},
                            "serverInfo": {"name": "rw-ast-tools", "version": "0.2.0"},
                        },
                    }
                elif method == "tools/list":
                    from ast_tools.tools import list_tools

                    tools = list_tools()
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "tools": [
                                {
                                    "name": t.name,
                                    "description": t.description,
                                    "inputSchema": getattr(t, "inputSchema", {}),
                                }
                                for t in tools
                            ]
                        },
                    }
                elif method == "tools/call":
                    from ast_tools.tools import get_tool_handler

                    params = request.get("params", {})
                    name = params.get("name")
                    arguments = params.get("arguments", {})
                    handler = get_tool_handler(name)
                    result = await anyio.to_thread.run_sync(handler, arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(result)}]
                        },
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}",
                        },
                    }

                writer.write((json.dumps(response) + "\n").encode("utf-8"))
                await writer.drain()
        except Exception as e:
            if not isinstance(e, (ConnectionResetError, BrokenPipeError)):
                logger.error("Client handler error: %s", e)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def accept_loop():
        """Accept client connections on the Unix socket."""
        loop = asyncio_mod.get_event_loop()
        server_sock.setblocking(False)
        while True:
            client_sock, _ = await loop.sock_accept(server_sock)
            reader, writer = await asyncio_mod.open_unix_connection(sock=client_sock)
            # Handle in background — concurrent clients
            asyncio_mod.create_task(
                handle_client(reader, writer)
            )

    try:
        await accept_loop()
    finally:
        server_sock.close()
        if os.path.exists(socket_path):
            os.unlink(socket_path)


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

        # Monkey-patch MCP SDK to be lenient about Accept headers
        # (Mistral, Cursor, etc. often omit Accept headers)
        try:
            from mcp.server.streamable_http import StreamableHTTPServerTransport
            async def lenient_validate(self, request, scope, send):
                return True
            StreamableHTTPServerTransport._validate_accept_header = lenient_validate
        except Exception:
            pass

        # Wrap in Starlette with lifespan to run the session manager
        @asynccontextmanager
        async def lifespan(_app):
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
        """Handle MCP request over HTTP."""
        from aiohttp import web

        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        # Forward to MCP server

        method = data.get("method")
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"experimental": {}, "tools": {"listChanged": False}},
                "serverInfo": {"name": "rw-ast-tools", "version": "1.28.0"},
            }
            return web.json_response(result)

        if method == "tools/list":
            from ast_tools.tools import list_tool_names

            return web.json_response({"tools": list_tool_names()})

        if method == "tools/call":
            name = data.get("params", {}).get("name")
            arguments = data.get("params", {}).get("arguments", {})
            handler = get_tool_handler(name)
            result = await anyio.to_thread.run_sync(handler, arguments)
            return web.json_response({"content": [{"type": "text", "text": json.dumps(result)}]})

        return web.json_response({"error": f"Unknown method: {method}"}, status=400)

    app = web.Application()
    app.router.add_post("/mcp", handle_mcp)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("Legacy HTTP server started on %s:%s", host, port)

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await runner.cleanup()


# ─── CLI Entry Point ─────────────────────────────────────────────────────


def main_sync() -> int:
    """Synchronous entry point for console_scripts."""
    import argparse

    parser = argparse.ArgumentParser(description="rw-ast-tools MCP Server")
    add_server_args(parser)
    parser.add_argument(
        "--foreground", action="store_true", help="Keep process in foreground (for systemd)"
    )
    args = parser.parse_args()
    config = config_from_args(args)

    mode = config["server"]["mode"]
    logger.info("Starting rw-ast-tools server in %s mode", mode)

    if mode == "timeout":
        anyio.run(_run_timeout_mode, config)
    elif mode == "daemon":
        anyio.run(_run_daemon_mode, config)
    elif mode == "remote":
        anyio.run(_run_remote_mode, config)
    else:
        logger.error("Unknown mode: %s", mode)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main_sync())
# Export for backward compatibility with tests
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Test-compatible wrapper for handle_call_tool."""
    return await handle_call_tool(name, arguments)
