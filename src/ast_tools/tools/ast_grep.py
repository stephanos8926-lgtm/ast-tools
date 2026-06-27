"""ast_grep tool — structural code search using ast-grep CLI."""

import json
import subprocess
from typing import Any


def _filter_top_level(matches: list, pattern: str) -> list:
    """Filter matches to only top-level definitions.

    This is a placeholder implementation — the actual filtering requires
    AST analysis to determine if a match is inside a class/function.
    For now, returns all matches unchanged.
    """
    # TODO: Implement proper top-level filtering using AST analysis
    return matches


def _tool_ast_grep(args: dict[str, Any]) -> dict[str, Any]:
    """Search code structurally using ast-grep CLI."""
    pattern = args["pattern"]
    path = args.get("path", ".")
    lang = args.get("lang")
    json_output = args.get("json_output", True)
    limit = min(int(args.get("limit", 50)), 500)
    count_only = args.get("count_only", False)
    top_level = args.get("top_level", False)

    cmd = ["ast-grep", "--pattern", pattern, path]
    if lang:
        cmd.extend(["--lang", lang])
    if json_output:
        cmd.append("--json")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return {
            "error": "ast-grep CLI not found. Install: cargo install ast-grep",
            "error_code": "NOT_FOUND",
            "tool": "ast_grep",
        }
    except subprocess.TimeoutExpired:
        return {
            "error": "ast-grep timed out after 30s",
            "error_code": "TIMEOUT",
            "tool": "ast_grep",
        }

    if proc.returncode != 0 and not proc.stdout:
        return {
            "error": proc.stderr.strip() or "ast-grep returned no output",
            "matches": [],
            "error_code": "PARSE_ERROR",
            "tool": "ast_grep",
        }

    if json_output:
        try:
            matches = json.loads(proc.stdout)
        except json.JSONDecodeError:
            matches = []
    else:
        lines = [line for line in proc.stdout.strip().splitlines() if line]
        matches = lines

    # Handle top_level filtering
    if top_level:
        matches = _filter_top_level(matches, pattern)

    total_matches = len(matches)

    # Count-only mode: return just the count
    if count_only:
        return {
            "count": total_matches,
            "pattern": pattern,
            "path": path,
            "top_level": top_level,
        }

    # Apply limit
    truncated = total_matches > limit
    if truncated:
        matches = matches[:limit]

    result: dict[str, Any] = {
        "matches": matches,
        "count": len(matches),
        "pattern": pattern,
        "path": path,
    }
    if truncated:
        result["truncated"] = True
        result["total_matches"] = total_matches
    return result
