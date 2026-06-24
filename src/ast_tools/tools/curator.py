#!/usr/bin/env python3
"""MCP tools for LLM curator service."""

from typing import Any, Optional
from pathlib import Path
from ..curator.daemon import LLmCurator, run_daily_audit, generate_summary


def _tool_curator_audit(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper for curator daily audit."""
    project_root = args.get("project_root", ".")
    auto_fix = args.get("auto_fix", True)
    return run_daily_audit(project_root)


def _tool_curator_summary(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper for generating project summary."""
    project_root = args.get("project_root", ".")
    output_path = args.get("output_path")
    
    summary = generate_summary(project_root, output_path)
    return {
        "summary": summary,
        "output_path": output_path or f"{project_root}/.ast-tools/summary.md"
    }


def _tool_curator_status(args: dict[str, Any]) -> dict[str, Any]:
    """Get curator status and last audit info."""
    import pathlib
    project_root = args.get("project_root", ".")
    summary_path = Path(project_root) / ".ast-tools" / "summary.md"
    
    status = {
        "project_root": project_root,
        "summary_exists": summary_path.exists(),
        "summary_age_days": None
    }
    
    if summary_path.exists():
        mtime = summary_path.stat().st_mtime
        import time
        age = (time.time() - mtime) / 86400
        status["summary_age_days"] = round(age, 1)
    
    return status


if __name__ == "__main__":
    # Quick test
    import pathlib
    print(_tool_curator_audit({"project_root": "."}))