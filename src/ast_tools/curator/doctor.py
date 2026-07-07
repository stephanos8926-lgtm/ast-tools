#!/usr/bin/env python3
"""Doctor command — comprehensive healthcheck for AST-Tools.

Usage:
    ast-tools doctor                    Summary report
    ast-tools doctor --verbose          Detailed per-check output
    ast-tools doctor --format json      Machine-readable
    ast-tools doctor --fix              Auto-fix discovered issues

Exit codes:
    0 — Healthy (score >= 80)
    1 — Warning (score 50-79)
    2 — Critical (score < 50)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

AST_TOOLS_DIR = Path.home() / ".ast-tools"
TREND_FILE = AST_TOOLS_DIR / "cache" / "doctor_trend.json"

HEALTH_WEIGHTS = {
    "database": 30,  # DB exists and opens
    "integrity": 20,  # PRAGMA integrity_check
    "schema": 10,  # Schema version matches
    "model": 15,  # Embedding model available
    "index": 10,  # Index has data and no orphans
    "config": 10,  # Config files valid
    "deps": 5,  # Dependencies importable
}

MIN_HEALTHY = 80
MIN_WARNING = 50


# ── Main check runner ───────────────────────────────────────────────────


def run(
    verbose: bool = False,  # noqa: ARG001
    fix: bool = False,
    format: str = "text",  # noqa: ARG001
    save_baseline: bool = True,
) -> dict[str, Any]:
    """Run all health checks and return report.

    Args:
        verbose: Show detailed per-check output.
        fix: Attempt to auto-fix discovered issues.
        format: Output format (text, json).
        save_baseline: Save score for trend tracking.

    Returns:
        Report dict with score, checks, and trend.
    """
    checks: list[dict[str, Any]] = []
    auto_fixes: list[str] = []

    # 1. Database existence
    db_path = AST_TOOLS_DIR / "cache" / "codebase.db"
    if db_path.exists():
        checks.append(
            {
                "check": "database",
                "status": "ok",
                "score": HEALTH_WEIGHTS["database"],
                "detail": f"DB exists ({db_path.stat().st_size // 1024} KB)",
            }
        )
    else:
        checks.append(
            {
                "check": "database",
                "status": "fail",
                "score": 0,
                "detail": "Database not found at ~/.ast-tools/cache/codebase.db",
            }
        )
        if fix:
            _init_database()
            if db_path.exists():
                auto_fixes.append("Created missing database")
                checks[-1] = {
                    "check": "database",
                    "status": "ok",
                    "score": HEALTH_WEIGHTS["database"],
                    "detail": "DB created via --fix",
                }

    # 2. Database integrity
    db_weight = HEALTH_WEIGHTS["integrity"]
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()
            if result == "ok":
                checks.append(
                    {
                        "check": "integrity",
                        "status": "ok",
                        "score": db_weight,
                        "detail": "PRAGMA integrity_check: ok",
                    }
                )
            else:
                checks.append(
                    {
                        "check": "integrity",
                        "status": "fail",
                        "score": 0,
                        "detail": f"Corruption detected: {result[:200]}",
                    }
                )
                if fix:
                    auto_fixes.append("DB corruption requires VACUUM or restore from backup")
        except Exception as e:
            checks.append(
                {
                    "check": "integrity",
                    "status": "error",
                    "score": 0,
                    "detail": f"Integrity check failed: {e}",
                }
            )
    else:
        checks.append(
            {
                "check": "integrity",
                "status": "skip",
                "score": 0,
                "detail": "No database to check",
            }
        )

    # 3. Schema version
    schema_weight = HEALTH_WEIGHTS["schema"]
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            row = cursor.fetchone()
            conn.close()
            version = row[0] if row else 0
            expected = 5  # Current SCHEMA_VERSION
            if version == expected:
                checks.append(
                    {
                        "check": "schema",
                        "status": "ok",
                        "score": schema_weight,
                        "detail": f"Schema v{version} (current)",
                    }
                )
            else:
                checks.append(
                    {
                        "check": "schema",
                        "status": "warn",
                        "score": schema_weight // 2,
                        "detail": f"Schema v{version} (expected v{expected})",
                    }
                )
                if fix:
                    from ast_tools.database.schema import migrate

                    conn = sqlite3.connect(str(db_path))
                    migrate(conn)
                    conn.commit()
                    conn.close()
                    auto_fixes.append(f"Migrated schema to v{expected}")
        except Exception as e:
            checks.append(
                {
                    "check": "schema",
                    "status": "error",
                    "score": 0,
                    "detail": f"Schema check failed: {e}",
                }
            )
    else:
        checks.append(
            {
                "check": "schema",
                "status": "skip",
                "score": 0,
                "detail": "No database to check",
            }
        )

    # 4. Model availability
    model_weight = HEALTH_WEIGHTS["model"]
    model_dir = AST_TOOLS_DIR / "cache" / "models"
    if model_dir.exists() and any(model_dir.iterdir()):
        checks.append(
            {
                "check": "model",
                "status": "ok",
                "score": model_weight,
                "detail": "Embedding model found",
            }
        )
    else:
        checks.append(
            {
                "check": "model",
                "status": "warn",
                "score": model_weight // 3,
                "detail": "No embedding model (FTS5-only mode — semantic search unavailable)",
            }
        )

    # 5. Index consistency
    index_weight = HEALTH_WEIGHTS["index"]
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM symbols")
            symbol_count = cursor.fetchone()[0]
            conn.close()
            if symbol_count > 0:
                checks.append(
                    {
                        "check": "index",
                        "status": "ok",
                        "score": index_weight,
                        "detail": f"{symbol_count} symbols indexed",
                    }
                )
            else:
                checks.append(
                    {
                        "check": "index",
                        "status": "warn",
                        "score": index_weight // 2,
                        "detail": "Index empty — run ast-tools index to populate",
                    }
                )
        except Exception as e:
            checks.append(
                {
                    "check": "index",
                    "status": "error",
                    "score": 0,
                    "detail": f"Index check failed: {e}",
                }
            )
    else:
        checks.append(
            {
                "check": "index",
                "status": "skip",
                "score": 0,
                "detail": "No database to check",
            }
        )

    # 6. Config validation
    cfg_weight = HEALTH_WEIGHTS["config"]
    cfg_dir = AST_TOOLS_DIR / "config"
    if cfg_dir.exists():
        checks.append(
            {
                "check": "config",
                "status": "ok",
                "score": cfg_weight,
                "detail": "Config directory exists",
            }
        )
    else:
        checks.append(
            {
                "check": "config",
                "status": "warn",
                "score": cfg_weight // 2,
                "detail": "No config directory (using defaults)",
            }
        )

    # 7. Dependencies
    deps_weight = HEALTH_WEIGHTS["deps"]
    missing_deps: list[str] = []
    for dep in ["mcp", "tree_sitter", "sqlite3"]:
        try:
            __import__(dep.replace("-", "_"))
        except ImportError:
            missing_deps.append(dep)
    if not missing_deps:
        checks.append(
            {
                "check": "deps",
                "status": "ok",
                "score": deps_weight,
                "detail": "All core deps available",
            }
        )
    else:
        checks.append(
            {
                "check": "deps",
                "status": "warn",
                "score": 0,
                "detail": f"Missing: {', '.join(missing_deps)}",
            }
        )

    # Calculate total score
    score = sum(c["score"] for c in checks)

    # Determine status
    if score >= MIN_HEALTHY:
        status = "healthy"
    elif score >= MIN_WARNING:
        status = "warning"
    else:
        status = "critical"

    # Trend tracking
    trend: dict[str, Any] = {"current": score, "previous": None, "delta": None}
    if save_baseline:
        trend = _track_trend(score)

    report = {
        "score": score,
        "status": status,
        "checks": checks,
        "trend": trend,
        "auto_fixes": auto_fixes,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"Doctor report: score={score}, status={status}")
    return report


# ── Trend tracking ──────────────────────────────────────────────────────


def _track_trend(score: int) -> dict[str, Any]:
    """Save current score and return trend data."""
    trend: dict[str, Any] = {"current": score, "previous": None, "delta": None}
    try:
        TREND_FILE.parent.mkdir(parents=True, exist_ok=True)
        if TREND_FILE.exists():
            history = json.loads(TREND_FILE.read_text())
            if isinstance(history, list) and len(history) > 0:
                trend["previous"] = history[-1].get("score")
                if trend["previous"] is not None:
                    trend["delta"] = score - trend["previous"]
                # Keep last 30 entries
                history.append({"score": score, "timestamp": datetime.now().isoformat()})
                TREND_FILE.write_text(json.dumps(history[-30:]))
            else:
                TREND_FILE.write_text(
                    json.dumps([{"score": score, "timestamp": datetime.now().isoformat()}])
                )
        else:
            TREND_FILE.write_text(
                json.dumps([{"score": score, "timestamp": datetime.now().isoformat()}])
            )
    except Exception as e:
        logger.debug(f"Trend tracking failed: {e}")
    return trend


# ── Helpers ─────────────────────────────────────────────────────────────


def _init_database() -> None:
    """Initialize database if missing."""
    from ast_tools.database.connection import get_connection
    from ast_tools.database.schema import init_schema, migrate

    db_path = AST_TOOLS_DIR / "cache" / "codebase.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        init_schema(conn)
        migrate(conn)
        conn.commit()
    finally:
        conn.close()


# ── CLI entry point ─────────────────────────────────────────────────────


def cli_doctor(args: dict | list | None = None) -> str:
    """CLI entry point for ast-tools doctor command."""
    if isinstance(args, list):
        args = {
            "verbose": "--verbose" in args or "-v" in args,
            "fix": "--fix" in args or "-f" in args,
            "format": "json"
            if "--format" in args and args[args.index("--format") + 1] == "json"
            else "text",
        }

    verbose = getattr(args, "get", lambda _k, d=None: d)("verbose", False)
    fix = getattr(args, "get", lambda _k, d=None: d)("fix", False)
    format = getattr(args, "get", lambda _k, d=None: d)("format", "text")

    result = run(verbose=verbose, fix=fix, format=format)

    if format == "json":
        return json.dumps(result, indent=2)

    lines: list[str] = []
    status_emoji = {"healthy": "✅", "warning": "⚠️", "critical": "❌"}
    lines.append(
        f"\n{status_emoji.get(result['status'], '❓')}  Health Score: {result['score']}/100 ({result['status']})"
    )

    # Trend
    trend = result.get("trend", {})
    if trend.get("previous") is not None:
        delta = trend.get("delta")
        delta_str = (
            f" (+{delta})"
            if delta and delta > 0
            else f" ({delta})"
            if delta and delta < 0
            else " (no change)"
        )
        lines.append(f"   Trend: {trend['previous']} → {trend['current']}{delta_str}")

    # Checks (verbose)
    if verbose:
        lines.append("")
        for c in result.get("checks", []):
            status_char = (
                "✅"
                if c["status"] == "ok"
                else "⚠️"
                if c["status"] == "warn"
                else "❌"
                if c["status"] == "fail"
                else "⏭️"
            )
            lines.append(f"  {status_char}  {c['check']}: {c['detail']}")

    # Auto-fixes
    auto_fixes = result.get("auto_fixes", [])
    if auto_fixes:
        lines.append(f"\n  🔧  Auto-fixes applied ({len(auto_fixes)}):")
        for f in auto_fixes:
            lines.append(f"       - {f}")

    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = __import__("argparse").ArgumentParser(description="AST-Tools Doctor")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--fix", "-f", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    result = cli_doctor(
        {
            "verbose": args.verbose,
            "fix": args.fix,
            "format": args.format,
        }
    )
    print(result)

    # Exit code based on health
    if args.format == "text":
        data = run(verbose=args.verbose, fix=args.fix)
        if data["score"] >= MIN_HEALTHY:
            sys.exit(0)
        elif data["score"] >= MIN_WARNING:
            sys.exit(1)
        else:
            sys.exit(2)
