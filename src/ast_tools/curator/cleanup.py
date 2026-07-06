#!/usr/bin/env python3
"""Cleanup command — remove temporary and stale files.

Usage:
    ast-tools cleanup                    Default cleanup
    ast-tools cleanup --aggressive       Also clear model cache
    ast-tools cleanup --dry-run          Preview only
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
    """Remove temporary and stale files.

    Args:
        aggressive: Also clear model cache.
        dry_run: Preview without modifying.

    Returns:
        Dict with freed space and details.
    """
    results: dict[str, Any] = {
        "freed_bytes": 0,
        "freed_human": "0 B",
        "operations": [],
        "warnings": [],
    }

    # 1. Delete cache/tmp/ contents
    tmp_dir = AST_TOOLS_DIR / "cache" / "tmp"
    if tmp_dir.exists():
        tmp_freed = _cleanup_tmp(tmp_dir, dry_run)
        results["freed_bytes"] += tmp_freed
        results["operations"].append({"op": "tmp_cleanup", "freed": tmp_freed})

    # 2. Remove expired caches (>7 days since last access)
    cache_dir = AST_TOOLS_DIR / "cache"
    if cache_dir.exists():
        cache_freed = _cleanup_expired_caches(cache_dir, dry_run, days=7)
        results["freed_bytes"] += cache_freed
        results["operations"].append({"op": "expired_cache", "freed": cache_freed})

    # 3. Delete stale log files (>30 days)
    log_dir = AST_TOOLS_DIR / "logs"
    if log_dir.exists():
        log_freed = _cleanup_stale_logs(log_dir, dry_run, retention_days=30)
        results["freed_bytes"] += log_freed
        results["operations"].append({"op": "stale_logs", "freed": log_freed})

    # 4. Aggressive: model cache
    if aggressive:
        model_dir = AST_TOOLS_DIR / "cache" / "models"
        if model_dir.exists():
            model_freed = _cleanup_models(model_dir, dry_run)
            results["freed_bytes"] += model_freed
            results["operations"].append({"op": "model_cache", "freed": model_freed})
            if model_freed > 0 and not dry_run:
                results["warnings"].append(
                    "Model cache cleared — run 'ast-tools init' to re-download"
                )

    results["freed_human"] = _human_size(results["freed_bytes"])
    return results


def _cleanup_tmp(tmp_dir: Path, dry_run: bool) -> int:
    """Remove all files in tmp directory."""
    total = 0
    for f in tmp_dir.iterdir():
        if f.is_file():
            total += f.stat().st_size
            if not dry_run:
                f.unlink()
    if total > 0 and not dry_run:
        logger.info(f"Cleaned tmp: {_human_size(total)}")
    return total


def _cleanup_expired_caches(cache_dir: Path, dry_run: bool, days: int = 7) -> int:
    """Remove cache files not accessed in N days."""
    total = 0
    cutoff = time.time() - days * 86400
    for f in cache_dir.rglob("*"):
        if f.is_file() and f.stat().st_atime < cutoff:
            total += f.stat().st_size
            if not dry_run:
                f.unlink()
    if total > 0 and not dry_run:
        logger.info(f"Removed expired caches: {_human_size(total)}")
    return total


def _cleanup_stale_logs(log_dir: Path, dry_run: bool, retention_days: int = 30) -> int:
    """Remove log files older than retention days."""
    total = 0
    cutoff = time.time() - retention_days * 86400
    for f in log_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            total += f.stat().st_size
            if not dry_run:
                f.unlink()
    if total > 0 and not dry_run:
        logger.info(f"Rotated stale logs: {_human_size(total)}")
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


def _human_size(bytes_val: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def cli_cleanup(args: dict | list | None = None) -> str:
    """CLI entry point."""
    if isinstance(args, list):
        args = {"aggressive": "--aggressive" in args or "-a" in args,
                 "dry_run": "--dry-run" in args or "-n" in args}
    aggressive = getattr(args, "get", lambda k, d=None: d)("aggressive", False)
    dry_run = getattr(args, "get", lambda k, d=None: d)("dry_run", False)

    result = run(aggressive=aggressive, dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    lines = [f"\n{prefix}Cleanup: {result['freed_human']}"]

    for w in result.get("warnings", []):
        lines.append(f"  ⚠️  {w}")

    for op in result.get("operations", []):
        if op["freed"] > 0:
            lines.append(f"  ✅ {op['op']}: {_human_size(op['freed'])} recovered")
        else:
            lines.append(f"  ➖ {op['op']}: nothing to clean")

    if dry_run:
        lines.append("\n  Run without --dry-run to apply.")
    else:
        lines.append(f"\n  ✅ {result['freed_human']} reclaimed.")

    return "\n".join(lines)
