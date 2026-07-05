#!/usr/bin/env python3
"""ast-tools-codebase-index: Codebase indexing + session intelligence tracking.

Adds code-intelligence behavior as Hermes plugin hooks:
- on_session_end: detects file mutations, calls codebase_summary via MCP, writes session intel
- CLI: `hermes index-watch` for watchdog file watcher
- Tools: codebase_index_refresh, codebase_index_status
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

version = "1.0.0"
description = "Automatic codebase indexing + session file mutation intelligence"
author = "RapidWebs Enterprise (Lucien)"
license = "MIT"
tags = ["ast", "codebase", "index", "intelligence", "semantic"]
requirements = ["watchdog"]


# ── Directories ──────────────────────────────────────────────────────────────

_SESSIONS_DIR = Path.home() / ".hermes" / "plugins" / "ast-tools-codebase-index" / "sessions"
_AST_TOOLS_SERVER = (
    Path.home() / "Workspaces" / "ast-tools" / ".venv" / "bin" / "python3"
)
_AST_TOOLS_SERVER_SCRIPT = (
    Path.home() / "Workspaces" / "ast-tools" / "src" / "ast_tools" / "_server.py"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mcp_call(method: str, params: dict | None = None) -> dict[str, Any] | None:
    """Call an ast-tools MCP tool via stdio subprocess.

    Sends a JSON-RPC request to the ast-tools MCP server and returns
    the parsed result. Best-effort — returns None on any failure.
    """
    if not _AST_TOOLS_SERVER.exists() or not _AST_TOOLS_SERVER_SCRIPT.exists():
        logger.debug("ast-tools MCP server not found — skipping call")
        return None

    init = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "hermes-codebase-index", "version": version}},
    })
    call = json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": method, "arguments": params or {}},
    })

    try:
        proc = subprocess.run(
            [str(_AST_TOOLS_SERVER), str(_AST_TOOLS_SERVER_SCRIPT)],
            input=f"{init}\n{call}\n",
            capture_output=True, text=True, timeout=30,
        )
        for line in proc.stdout.strip().split("\n"):
            try:
                resp = json.loads(line)
                if resp.get("id") == 2:
                    result = resp.get("result", {})
                    content = result.get("content", [])
                    if content:
                        text = content[0].get("text", "")
                        return json.loads(text) if text.startswith("{") else {"text": text}
                    return result
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
    except Exception as exc:
        logger.warning("MCP call %s failed: %s", method, exc)
    return None


# ── Code Intelligence: on_session_end hook ────────────────────────────────────

MUTATION_TOOLS = {"write_file", "edit_file", "patch", "ast_edit"}


def _extract_modified_files(context: Any) -> list[str]:
    """Return deduplicated list of files written during the session."""
    mutated: list[str] = []
    seen: set[str] = set()

    for call in context.get("tool_calls", []):
        if not isinstance(call, dict):
            continue
        name = call.get("name", "")
        if name not in MUTATION_TOOLS:
            continue
        args = call.get("arguments", {})
        if not isinstance(args, dict):
            continue
        for key in ("path", "file"):
            fp = args.get(key)
            if fp and isinstance(fp, str) and fp not in seen:
                seen.add(fp)
                mutated.append(fp)

    return mutated


def _call_codebase_summary(cwd: str = "") -> dict[str, Any] | None:
    """Invoke ast-tools codebase_summary via MCP (best-effort)."""
    return _mcp_call("codebase_summary", {"cwd": cwd or "."})


def _write_session_intel(
    session_id: str,
    modified_files: list[str],
    summary: dict[str, Any] | None,
) -> None:
    """Persist a session-intelligence record."""
    record: dict[str, Any] = {
        "timestamp": _now_iso(),
        "session_id": session_id,
        "modified_files": modified_files,
        "summary": summary,
    }
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    out = _SESSIONS_DIR / f"{session_id}.json"
    try:
        out.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.debug("Wrote session intelligence to %s", out)
    except OSError as e:
        logger.warning("Could not write session intelligence: %s", e)


def _on_session_end(
    session_id: str = "",
    completed: bool = True,
    **kwargs: Any,
) -> None:
    """on_session_end: detect file mutations, call codebase_summary."""
    if not completed:
        return

    if not session_id:
        session_id = kwargs.get("session_id", "unknown")

    working_dir = kwargs.get("working_dir", "") or kwargs.get("cwd", "")
    tool_calls = kwargs.get("tool_calls", [])

    # Detect file mutations
    modified_files = _extract_modified_files({"tool_calls": tool_calls})
    if not modified_files:
        logger.debug("No file modifications in this session")
        return

    logger.info(
        "Session %s: %d file(s) modified — fetching codebase summary",
        session_id, len(modified_files),
    )

    # Get structural summary (best-effort)
    summary = _call_codebase_summary(cwd=working_dir)

    # Persist
    _write_session_intel(session_id, modified_files, summary)
    logger.info("Session intelligence written for %s", session_id)


# ── File Watcher (watchdog) ──────────────────────────────────────────────────


class CodebaseIndexHandler(FileSystemEventHandler):
    """Handle file system events for codebase indexing."""

    def __init__(self):
        super().__init__()
        self._debounce_timer = None
        self._debounce_delay = 0.5

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.py'):
            return
        if '__pycache__' in event.src_path or '.git' in event.src_path:
            return
        logger.info("File modified: %s", event.src_path)
        self._schedule_reindex(event.src_path)

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith('.py'):
            return
        if '__pycache__' in event.src_path or '.git' in event.src_path:
            return
        logger.info("File created: %s", event.src_path)
        self._schedule_reindex(event.src_path)

    def on_deleted(self, event):
        if event.is_directory or not event.src_path.endswith('.py'):
            return
        if '__pycache__' in event.src_path or '.git' in event.src_path:
            return
        self._schedule_reindex(None)

    def _schedule_reindex(self, file_path: str | bytes | None):
        """Schedule an incremental reindex via MCP."""
        logger.info("Triggering incremental reindex for: %s", file_path or "full project")
        try:
            result = _mcp_call("refresh_index", {
                "project_path": str(Path.cwd()),
                "force": False,
                "embeddings": False,
            })
            if result:
                logger.debug("Reindex result: %s", result)
        except Exception as exc:
            logger.warning("Auto-reindex failed: %s", exc)


# ── CLI ──────────────────────────────────────────────────────────────────────


def start_watcher_cli(args):
    """CLI command to start the file watcher daemon."""
    project_path = args.get('project_path', '.') if isinstance(args, dict) else '.'
    if isinstance(args, list) and len(args) > 0:
        project_path = args[0]

    root = Path(project_path).resolve()
    if not root.exists():
        return f"Error: Path does not exist: {root}"

    handler = CodebaseIndexHandler()
    observer = Observer()
    observer.schedule(handler, str(root), recursive=True)
    observer.start()

    logger.info("Watching %s for Python file changes...", root)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    return "Watcher stopped"


def refresh_index_handler(args):
    """Tool handler for manual index refresh."""
    project_path = args.get('project_path', '.')
    force = args.get('force', False)
    result = _mcp_call("refresh_index", {"project_path": project_path, "force": force})
    return json.dumps(result, indent=2) if result else "No result from MCP server"


def status_handler(args):
    """Tool handler for index status."""
    result = _mcp_call("index_status", {})
    return json.dumps(result, indent=2) if result else "ast-tools MCP server not available"


# ── Plugin Registration ──────────────────────────────────────────────────────


def register(ctx) -> None:
    """Register codebase-index hooks and tools."""
    # Register CLI command
    ctx.register_cli_command("index-watch", start_watcher_cli)

    # Register tools
    ctx.register_tool("codebase_index_refresh", refresh_index_handler)
    ctx.register_tool("codebase_index_status", status_handler)

    # Register session intelligence hook
    ctx.register_hook("on_session_end", _on_session_end)

    logger.info(
        "ast-tools-codebase-index v%s registered — 1 hook (on_session_end), "
        "2 tools, 1 CLI, watchdog file watcher",
        version,
    )