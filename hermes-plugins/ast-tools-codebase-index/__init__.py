#!/usr/bin/env python3
"""ast-tools-codebase-index: Codebase indexing + session intelligence tracking.

Adds code-intelligence behavior as Hermes plugin hooks:
- on_session_end: detects file mutations, calls codebase_summary, writes session intel
- CLI: `hermes index-watch` for watchdog file watcher
- Tools: codebase_index_refresh, codebase_index_status

Absorbs: hooks/code-intelligence/{handler.py, HOOK.yaml}

Author: RapidWebs (Lucien)
License: MIT
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    try:
        import mcp_ast_tools  # type: ignore[import-not-found]

        result = mcp_ast_tools.codebase_summary(cwd=cwd or ".")
        if result is None:
            return None
        if isinstance(result, str):
            return json.loads(result)
        return result
    except ImportError:
        logger.debug("mcp_ast_tools not available — skipping summary")
        return None
    except Exception as exc:
        logger.warning("codebase_summary failed: %s", exc)
        return None


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
    """on_session_end: detect file mutations, call codebase_summary.

    Replaces: hooks/code-intelligence handler.py
    """
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

    def __init__(self, index_tool=None):
        super().__init__()
        self.index_tool = index_tool
        self._debounce_timer = None
        self._debounce_delay = 0.5

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.py'):
            return
        if '__pycache__' in event.src_path or '.git' in event.src_path:
            return
        logger.info(f"File modified: {event.src_path}")
        self._schedule_reindex(event.src_path)

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith('.py'):
            return
        if '__pycache__' in event.src_path or '.git' in event.src_path:
            return
        logger.info(f"File created: {event.src_path}")
        self._schedule_reindex(event.src_path)

    def on_deleted(self, event):
        if event.is_directory or not event.src_path.endswith('.py'):
            return
        if '__pycache__' in event.src_path or '.git' in event.src_path:
            return
        self._schedule_reindex(None)

    def _schedule_reindex(self, file_path):
        # Placeholder for real indexing logic
        logger.info(f"Would reindex: {file_path or 'full project'}")


# ── CLI ──────────────────────────────────────────────────────────────────────


def start_watcher_cli(args):
    """CLI command to start the file watcher."""
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

    logger.info(f"Watching {root} for Python file changes...")
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

    try:
        from ast_tools._server import call_tool
        import asyncio

        async def run():
            result = await call_tool('refresh_index', {'path': project_path, 'force': force})
            return result[0].text if result else 'No result'

        return asyncio.run(run())
    except ImportError:
        return "ast_tools._server not available — run ast-tools MCP server first"


def status_handler(args):
    """Tool handler for index status."""
    try:
        from ast_tools._server import call_tool
        import asyncio

        async def run():
            result = await call_tool('index_status', {})
            return result[0].text if result else 'No result'

        return asyncio.run(run())
    except ImportError:
        return "ast_tools._server not available"


# ── Plugin Registration ──────────────────────────────────────────────────────


def register(ctx) -> None:
    """Register codebase-index hooks and tools.

    Ports: hooks/code-intelligence/{handler.py, HOOK.yaml}
    """
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
