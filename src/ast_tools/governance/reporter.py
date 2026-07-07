"""Governance reporter — format violations as text or HTML."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scanner import Violation


def format_violations(
    violations: list[Violation],
    format: str = "text",
    fail_on: str = "error",
) -> str:
    """Format violations as text or JSON.

    Args:
        violations: List of violations.
        format: "text" or "json".
        fail_on: Minimum severity to include ("error" or "warn").

    Returns:
        Formatted string.
    """
    filtered = [v for v in violations if fail_on == "warn" or v.severity == "error"]

    if format == "json":
        import json

        return json.dumps([v.to_dict() for v in filtered], indent=2)

    if not filtered:
        return "✅ No governance violations found."

    lines = [f"❌ {len(filtered)} governance violation(s):\n"]
    for v in filtered:
        icon = "⚠️" if v.severity == "warn" else "❌"
        lines.append(f"  {icon} {v.to_dict()['message']}")

    # Summary by severity
    errors = sum(1 for v in filtered if v.severity == "error")
    warns = sum(1 for v in filtered if v.severity == "warn")
    lines.append(f"\n  Summary: {errors} errors, {warns} warnings")

    return "\n".join(lines)


def generate_report_html(violations: list[Violation]) -> str:
    """Generate an HTML report of findings (for --report subcommand)."""
    rows = "".join(
        f"<tr><td>{v.file}</td><td>{v.layer}</td>"
        f"<td>{v.import_target}</td><td>{v.target_layer or '?'}</td>"
        f"<td><span class='badge badge-{v.severity}'>{v.severity}</span></td></tr>"
        for v in violations
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Architecture Governance Report</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
.badge-error {{ background: #fcc; padding: 2px 6px; border-radius: 3px; }}
.badge-warn {{ background: #ffc; padding: 2px 6px; border-radius: 3px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #f5f5f5; }}
</style>
</head>
<body>
<h1>Architecture Governance Report</h1>
<p>{len(violations)} violation(s) found</p>
<table>
<thead><tr><th>File</th><th>Layer</th><th>Import</th><th>Target Layer</th><th>Severity</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</body>
</html>"""
