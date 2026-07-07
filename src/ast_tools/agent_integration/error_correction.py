"""Error correction — detect common AST-tools usage errors and provide guidance.

Extracted from the Hermes ast-tools-tokens plugin (post_tool_call hook).
Zero Hermes dependency — pure functions usable by any agent framework.

Usage:
    from ast_tools.agent_integration import correct_tool_error

    # After a tool call returns an error:
    correction = correct_tool_error("ast_edit", result_text)
    if correction:
        print(correction)  # "Always dry_run=true first!"
"""

from __future__ import annotations

# ── Error correction patterns ───────────────────────────────────────────

ERROR_PATTERNS: dict[str, dict[str, str]] = {
    "ast_edit": {
        "Invalid operation": (
            "**Correct usage:** ast_edit operations:\n"
            '- `rename_function`: {"function": "old_name", "new_name": "new_name"}\n'
            '- `replace_node`: {"pattern": "old", "replacement": "new"}\n'
            '- `insert_after`: {"anchor": "func", "code": "new code"}\n'
            '- `add_parameter`: {"function": "foo", "param": "bar", "type": "str"}\n'
            "Always dry_run=true first!"
        ),
        "dry_run": "⚠️ Always run dry_run=true FIRST to preview changes.",
    },
    "semantic_search": {
        "k exceeds": ("⚠️ k=50 is large. Use k=10 + diversity_limit=5 or add lang='python' filter."),
        "no results": "Try broader query or remove kind/lang filters.",
    },
    "ast_grep": {
        "Invalid pattern": (
            "Use $VAR for single node, $$$VAR for multiple. Example: def $FUNC($$$ARGS)"
        ),
    },
    "impact_analysis": {
        "symbol not found": (
            "Use find_references first to locate symbol, then impact_analysis on the file."
        ),
    },
}


def _strip_prefix(tool_name: str) -> str:
    """Strip MCP prefix from tool names for pattern lookup."""
    prefixes = ["mcp_ast_tools_tool_", "mcp_ast_tools_"]
    for prefix in prefixes:
        if tool_name.startswith(prefix):
            return tool_name[len(prefix) :]
    return tool_name


def get_error_correction(tool_name: str, result_text: str) -> str | None:
    """Get a usage correction for a failed tool call.

    Args:
        tool_name: Name of the tool that returned an error.
        result_text: The result text containing the error message.

    Returns:
        A guidance string if a matching correction is found, None otherwise.
    """
    raw = _strip_prefix(tool_name)

    # Check if result looks like an error
    if "Error:" not in str(result_text) and "error" not in str(result_text).lower()[:50]:
        return None

    patterns = ERROR_PATTERNS.get(raw, {})
    for pattern, correction in patterns.items():
        if pattern.lower() in str(result_text).lower():
            return _format_correction(correction)

    # Generic fallback
    if raw in ERROR_PATTERNS:
        return _format_correction(f"Check docs for {raw}.")

    return None


def correct_tool_error(tool_name: str, result_text: str) -> dict | None:
    """Check a tool result for common errors and return context correction.

    This is the main entry point — returns a dict compatible with
    Hermes pre_llm_call context injection, or a plain dict for other agents.

    Args:
        tool_name: The name of the tool that was called.
        result_text: The result/output text from the tool call.

    Returns:
        Dict with 'context' key if error detected, None otherwise.
    """
    correction = get_error_correction(tool_name, result_text)
    if correction:
        return {"context": f"\n⚠️ **AST-Tools Usage Correction:**\n{correction}\n"}
    return None


def _format_correction(text: str) -> str:
    """Format a correction string with consistent wrapping."""
    if text.startswith("⚠️") or text.startswith("**"):
        return text
    return f"**Tip:** {text}"
