"""Session intelligence — codebase mutation tracking and summary retrieval.

Extracted from the Hermes ast-tools-codebase-index plugin (on_session_end hook).
Zero Hermes dependency — pure functions usable by any agent framework.

Usage:
    from ast_tools.agent_integration import (
        extract_modified_files,
        call_codebase_summary,
        write_session_intel,
    )
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

MUTATION_TOOLS = frozenset({"write_file", "edit_file", "patch", "ast_edit"})

# Default server paths (can be overridden via kwargs)
DEFAULT_SERVER_PYTHON = Path.home() / "Workspaces" / "ast-tools" / ".venv" / "bin" / "python3"
DEFAULT_SERVER_SCRIPT = (
    Path.home() / "Workspaces" / "ast-tools" / "src" / "ast_tools" / "_server.py"
)


# ── Public API ──────────────────────────────────────────────────────────


def extract_modified_files(tool_calls: list[dict[str, Any]]) -> list[str]:
    """Extract deduplicated list of file paths from session tool calls.

    Args:
        tool_calls: List of tool call records from the session context.

    Returns:
        Deduplicated list of file paths that were written/modified.
    """
    mutated: list[str] = []
    seen: set[str] = set()

    for call in tool_calls:
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


def call_codebase_summary(
    cwd: str = "",
    server_python: Path | None = None,
    server_script: Path | None = None,
) -> dict[str, Any] | None:
    """Call the ast-tools codebase_summary via MCP over stdio.

    Args:
        cwd: Working directory for the codebase summary.
        server_python: Path to the Python interpreter (auto-detected).
        server_script: Path to the MCP server script (auto-detected).

    Returns:
        Parsed result dict, or None on failure.
    """
    python_exe = server_python or DEFAULT_SERVER_PYTHON
    script = server_script or DEFAULT_SERVER_SCRIPT

    if not python_exe.exists() or not script.exists():
        logger.debug("ast-tools MCP server not found — skipping call")
        return None

    init = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent-integration", "version": "1.0.0"},
            },
        }
    )
    call = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "codebase_summary", "arguments": {"cwd": cwd or "."}},
        }
    )

    try:
        proc = subprocess.run(
            [str(python_exe), str(script)],
            input=f"{init}\n{call}\n",
            capture_output=True,
            text=True,
            timeout=30,
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
        logger.warning("MCP call codebase_summary failed: %s", exc)

    return None


def write_session_intel(
    session_id: str,
    modified_files: list[str],
    summary: dict[str, Any] | None = None,
    output_dir: Path | None = None,
) -> str | None:
    """Persist a session-intelligence record to disk.

    Args:
        session_id: Unique session identifier.
        modified_files: List of files modified during the session.
        summary: Optional codebase summary result.
        output_dir: Directory to write records to (auto-created).

    Returns:
        Path to the written file, or None on failure.
    """
    out_dir = output_dir or (
        Path.home() / ".hermes" / "plugins" / "ast-tools-codebase-index" / "sessions"
    )

    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "modified_files": modified_files,
        "summary": summary,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{session_id}.json"

    try:
        out_path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.debug("Wrote session intelligence to %s", out_path)
        return str(out_path)
    except OSError as e:
        logger.warning("Could not write session intelligence: %s", e)
        return None
