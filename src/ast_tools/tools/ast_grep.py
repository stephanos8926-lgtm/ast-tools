"""ast_grep tool — structural code search using ast-grep CLI."""

import json
import subprocess
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=128)
def _compile_pattern(pattern: str, lang: str | None) -> tuple[str, str | None]:
    """Compile AST pattern and cache it.

    In a real scenario, this would return a compiled AST object.
    Here, it returns a tuple representing the pattern and language.
    """
    return pattern, lang


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
    cache_stats = args.get("cache_stats", False)

    # Compile pattern and cache it
    _compiled_pattern, _compiled_lang = _compile_pattern(pattern, lang)

    cmd = ["ast-grep", "--pattern", pattern, path] # Use original pattern for CLI
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
        stderr = proc.stderr.strip() or "ast-grep returned no output"

        # Provide helpful pattern syntax hints
        hints = []
        if "$" not in pattern:
            hints.append("Patterns use $ for meta-variables. Example: $FUNC for a name, $$$ARGS for multiple args.")
        if "def " in pattern and "$" in pattern:
            hints.append("Python pattern syntax: def $FUNC($$$ARGS) or class $CLASS")
        if "function" in pattern.lower() and "$" in pattern:
            hints.append("TypeScript/JS pattern: function $NAME($$$ARGS) or const $NAME = ($$$ARGS)")
        if "returncode" in stderr.lower() or "parse" in stderr.lower():
            hints.append("Common fixes: wrap strings in quotes, use $$$ for multiple nodes, ensure valid AST structure")
        if "no matches" in stderr.lower():
            hints.append("Try a simpler pattern first, or check that the language (--lang) matches your code")

        error_response = {
            "error": stderr,
            "matches": [],
            "error_code": "PARSE_ERROR" if "parse" in stderr.lower() else "EXECUTION_ERROR",
            "tool": "ast_grep",
        }

        if hints:
            error_response["hints"] = hints
            error_response["suggestion"] = "See https://ast-grep.github.io/guide/pattern-syntax.html for full syntax"

        return error_response

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

    if cache_stats:
        result["cache_info"] = {
            "hits": _compile_pattern.cache_info().hits,
            "misses": _compile_pattern.cache_info().misses,
            "current_size": _compile_pattern.cache_info().currsize,
        }
    return result

