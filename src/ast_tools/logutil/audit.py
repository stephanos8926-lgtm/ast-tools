"""Audit trail logger with secret pattern filtering."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ast_tools.config.loader import get_config_dir

AUDIT_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r'(?i)(api[_\-]?key|secret|password|token)\s*[:=]\s*[\'"][^\'"]+[\'"]'),
    re.compile(r"[A-Za-z0-9]{32,}"),
]

AUDIT_LOG_PATH: Path = get_config_dir() / "logs" / "audit.jsonl"


def _redact_secrets(data: dict) -> dict:
    """Redact potential secrets from a params dict."""
    safe: dict = {}
    for k, v in data.items():
        sv = str(v)
        for pattern in AUDIT_SECRET_PATTERNS:
            sv = pattern.sub("[REDACTED]", sv)
        safe[k] = sv
    return safe


def _sanitize(result: str) -> str:
    """Truncate overly long results."""
    result = str(result)
    if len(result) > 500:
        result = result[:500] + "..."
    return result


def write_audit(
    action: str, params: dict | None = None, result: str = "", user: str = "agent"
) -> None:
    """Write a JSONL entry to the audit log.

    Args:
        action: What was done (e.g. "config_validate", "index_refresh").
        params: Parameters passed to the action (secrets redacted).
        result: Outcome summary.
        user: Who performed the action.
    """
    safe_params = _redact_secrets(params or {})
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "params": safe_params,
        "result": _sanitize(result),
        "user": user,
    }
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


class AuditLogger:
    """Static audit logger for convenience."""

    @staticmethod
    def log(
        action: str, params: dict | None = None, result: str = "", user: str = "agent"
    ) -> None:
        write_audit(action, params, result, user)
