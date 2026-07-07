#!/usr/bin/env python3
"""Vacuum command — space reclamation for AST-Tools.

Usage:
    ast-tools vacuum                    Default vacuum
    ast-tools vacuum --aggressive       Also clear model cache
    ast-tools vacuum --dry-run          Show what would be freed
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AST_TOOLS_DIR = Path.home() / ".ast-tools"


def run(aggressive: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """Reclaim disk space.

    Args:
        aggressive: Also clear model cache.
        dry_run: Show what would be freed without modifying.

    Returns:
        Dict with freed space and details.
    """
    results: dict[str, Any] = {
        "freed_bytes": 0,
        "freed_human": "0 B",
        "operations": [],
        "warnings": [],
    }

    # 1. SQLite VACUUM + REINDEX
    db_path = AST_TOOLS_DIR / "cache" / "codebase.db"
    if db_path.exists():
        before = db_path.stat().st_size
        if not dry_run:
            _check_disk_space(db_path, before)
            _vacuum_db(db_path)
        after = db_path.stat().st_size if not dry_run else before
        freed = before - after
        results["freed_bytes"] += freed
        results["operations"].append({
            "op": "vacuum",
            "before": before,
            "after": after,
            "freed": freed,
        })

    # 2. Temp file cleanup
    tmp_dir = AST_TOOLS_DIR / "cache" / "tmp"
    if tmp_dir.exists():
        tmp_freed = _cleanup_tmp(tmp_dir, dry_run)
        results["freed_bytes"] += tmp_freed
        results["operations"].append({
            "op": "tmp_cleanup",
            "freed": tmp_freed,
        })

    # 3. Log rotation (>30 day old logs)
    log_dir = AST_TOOLS_DIR / "logs"
    if log_dir.exists():
        log_freed = _rotate_logs(log_dir, dry_run)
        results["freed_bytes"] += log_freed
        results["operations"].append({
            "op": "log_rotation",
            "freed": log_freed,
        })

    # 4. Aggressive: model cache
    if aggressive:
        model_dir = AST_TOOLS_DIR / "cache" / "models"
        if model_dir.exists():
            model_freed = _cleanup_models(model_dir, dry_run)
            results["freed_bytes"] += model_freed
            results["operations"].append({
                "op": "model_cache",
                "freed": model_freed,
            })
            if model_freed > 0 and not dry_run:
                results["warnings"].append(
                    "Model cache cleared — run 'ast-tools init' to re-download"
                )

    results["freed_human"] = _human_size(results["freed_bytes"])
    return results


def _check_disk_space(db_path: Path, db_size: int) -> None:
    """Verify sufficient free space for VACUUM (needs ~2x DB size)."""
    free = shutil.disk_usage(db_path.parent).free
    if free < db_size * 2:
        raise RuntimeError(
            f"Insufficient disk space for VACUUM: need {_human_size(db_size * 2)}, "
            f"have {_human_size(free)}. Free up space and retry."
        )


def _vacuum_db(db_path: Path) -> None:
    """Run SQLite VACUUM + REINDEX."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("VACUUM")
        conn.execute("REINDEX")
        conn.commit()
    finally:
        conn.close()
    logger.info(f"Vacuumed {db_path}")


def _cleanup_tmp(tmp_dir: Path, dry_run: bool) -> int:
    """Remove temporary files."""
    total = 0
    for f in tmp_dir.iterdir():
        if f.is_file():
            total += f.stat().st_size
            if not dry_run:
                f.unlink()
    if not dry_run:
        logger.info(f"Cleaned tmp: {_human_size(total)}")
    return total


def _rotate_logs(log_dir: Path, dry_run: bool, retention_days: int = 30) -> int:
    """Remove logs older than retention_days."""
    total = 0
    cutoff = time.time() - retention_days * 86400
    for f in log_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            total += f.stat().st_size
            if not dry_run:
                f.unlink()
    if total > 0 and not dry_run:
        logger.info(f"Rotated logs: {_human_size(total)}")
    return total


def _cleanup_models(model_dir: Path, dry_run: bool) -> int:
    """Remove cached model files."""
    total = 0
    for f in model_dir.iterdir():
        if f.is_dir():
            for sub in f.rglob("*"):
                if sub.is_file():
                    total += sub.stat().st_size
            if not dry_run:
                shutil.rmtree(f, ignore_errors=True)
    return total


def _human_size(bytes: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} TB"


def cli_vacuum(args: dict | list | None = None) -> str:
    """CLI entry point."""
    if isinstance(args, list):
        args = {
            "aggressive": "--aggressive" in args or "-a" in args,
            "dry_run": "--dry-run" in args or "-n" in args,
        }
    aggressive = getattr(args, "get", lambda _k, d=None: d)("aggressive", False)
    dry_run = getattr(args, "get", lambda _k, d=None: d)("dry_run", False)

    result = run(aggressive=aggressive, dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    lines = [f"\n{prefix}Space Reclamation: {result['freed_human']}"]

    if result["warnings"]:
        for w in result["warnings"]:
            lines.append(f"  ⚠️  {w}")

    if result["operations"]:
        for op in result["operations"]:
            if op["freed"] > 0:
                lines.append(f"  ✅ {op['op']}: {_human_size(op['freed'])} recovered")
            else:
                lines.append(f"  - {op['op']}: nothing to free")

    if dry_run:
        lines.append("\n  Run without --dry-run to apply.")
    else:
        lines.append(f"\n  ✅ Done. {result['freed_human']} freed.")

    return "\n".join(lines)
