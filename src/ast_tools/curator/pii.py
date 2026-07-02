#!/usr/bin/env python3
"""PII detection and redaction for AST-Tools curator.

Detects common sensitive patterns in symbol names, docstrings, and comments.
Configurable action: flag (default — audit only), redact (replace with [REDACTED]),
remove (delete the symbol).

Default mode is "flag" — NEVER auto-removes. All flags are logged to audit trail.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── PII patterns ───────────────────────────────────────────────────────

PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[\w\.\-]+@[\w\.\-]+\.\w+"),
    "api_key": re.compile(r"(?i)(api[_\-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]+['\"]"),
    "file_path": re.compile(r"(?:/home/|/Users/|C:\\|/var/|/etc/)[^\s]+"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,40}"),
    "private_key_marker": re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
}

# Fields in Symbol dataclass to scan for PII
SCAN_FIELDS = ["name", "qualified_name", "signature", "docstring"]


# ── Main scan function ─────────────────────────────────────────────────


def scan_symbols(
    conn,
    action: str = "flag",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Scan all symbols for PII patterns.

    Args:
        conn: Database connection.
        action: What to do on match (flag, redact, remove).
        dry_run: Preview only, no modifications.

    Returns:
        Report with findings by pattern type and severity.
    """
    findings: dict[str, Any] = {k: [] for k in PII_PATTERNS}
    findings["total"] = 0
    findings["action"] = action
    findings["dry_run"] = dry_run

    try:
        cursor = conn.execute("SELECT id, name, qualified_name, signature, docstring FROM symbols")
        for row in cursor.fetchall():
            symbol_id, name, qname, sig, doc = row

            for pattern_name, regex in PII_PATTERNS.items():
                for field, value in [
                    ("name", name), ("qualified_name", qname),
                    ("signature", sig or ""), ("docstring", doc or ""),
                ]:
                    if not value:
                        continue
                    matches = regex.findall(str(value))
                    if matches:
                        finding = {
                            "symbol_id": symbol_id,
                            "symbol_name": name,
                            "pattern": pattern_name,
                            "field": field,
                            "matches": matches[:3],  # Limit to 3 per field
                        }
                        findings[pattern_name].append(finding)
                        findings["total"] += 1

                        # Apply action
                        if action == "redact" and not dry_run:
                            redacted = regex.sub("[REDACTED]", str(value))
                            if field == "name":
                                conn.execute("UPDATE symbols SET name = ? WHERE id = ?", (redacted, symbol_id))
                            elif field == "qualified_name":
                                conn.execute("UPDATE symbols SET qualified_name = ? WHERE id = ?", (redacted, symbol_id))
                            elif field == "signature":
                                conn.execute("UPDATE symbols SET signature = ? WHERE id = ?", (redacted, symbol_id))
                        elif action == "remove" and not dry_run:
                            conn.execute("DELETE FROM symbols WHERE id = ?", (symbol_id,))
                            break  # No need to check other fields

                if action == "remove" and not dry_run:
                    continue  # Already deleted, skip remaining patterns

        conn.commit()

        # Log summary
        logger.info(
            f"PII scan: {findings['total']} findings "
            f"(action={action}, dry_run={dry_run})"
        )

    except Exception as e:
        logger.error(f"PII scan failed: {e}")
        findings["error"] = str(e)

    return findings


def format_findings(findings: dict[str, Any]) -> str:
    """Format PII scan findings as a readable report."""
    lines: list[str] = []
    prefix = "[DRY RUN] " if findings.get("dry_run") else ""
    lines.append(f"\n{prefix}PII Scan Results")
    lines.append(f"  Action: {findings.get('action', 'flag')}")

    if findings.get("error"):
        lines.append(f"  ❌ Error: {findings['error']}")
        return "\n".join(lines)

    if findings["total"] == 0:
        lines.append("  ✅ No PII detected in symbol database")
        return "\n".join(lines)

    lines.append(f"  🔍 {findings['total']} potential hits found")

    for pattern_name, hits in sorted(findings.items()):
        if not isinstance(hits, list) or pattern_name in ("total", "action", "dry_run", "error"):
            continue
        if hits:
            lines.append(f"\n  [{pattern_name}] {len(hits)} hit(s):")
            for h in hits[:5]:  # Show first 5 per pattern
                lines.append(f"      {h['symbol_name']} ({h['field']}): {h['matches'][0]}")
            if len(hits) > 5:
                lines.append(f"      ... and {len(hits) - 5} more")

    return "\n".join(lines)


CLI_PII_DESCRIPTION = "Scan and optionally redact PII from symbol database"