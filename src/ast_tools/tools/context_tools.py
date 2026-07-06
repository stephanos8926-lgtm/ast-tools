"""Context injection MCP tools for ast-tools.

Provides MCP tools for manual context injection, token tracking,
and usage validation. Backed by agent_integration modules — no Hermes dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ast_tools.agent_integration import (
    build_ast_tools_context,
    correct_tool_error,
    detect_ast_query,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def _tool_context_inject(args: dict[str, Any]) -> dict[str, Any]:
    """Inject relevant AST-tools context based on a query.

    Parameters:
        query: The user's query to match against AST-tools keywords.
        current_file: Optional current file path for context scoping.

    Returns:
        Dict with status and context payload.
    """
    query = args.get("query", "")
    current_file = args.get("current_file")

    if not query:
        return {
            "status": "no_query",
            "message": "No query provided — supply a 'query' parameter.",
        }

    is_relevant = detect_ast_query(query)
    if not is_relevant:
        return {
            "status": "not_relevant",
            "message": "Query doesn't appear to relate to AST-tools operations.",
            "context": None,
        }

    context = build_ast_tools_context(query)
    return {
        "status": "injected",
        "message": f"Context injected for query: '{query}' (file: {current_file or 'none'})",
        "context_length": len(context),
        "estimated_tokens": len(context) // 4,
        "context": context,
    }


def _tool_context_status(args: dict[str, Any]) -> dict[str, Any]:
    """Get context injection system status."""
    _ = args  # unused, kept for signature compatibility
    return {
        "status": "available",
        "module": "ast_tools.agent_integration.context_builder",
        "tools": ["context_inject", "token_status", "validate_usage"],
        "context_sources": "static (keywords-based)",
        "estimated_context_size_tokens": 600,
    }


def _tool_token_status(args: dict[str, Any]) -> dict[str, Any]:
    """Get current token budget status for ast-tools tools.

    Parameters:
        tool_name: Optional — get budget info for a specific tool.
        result_length: Optional — check if a result would exceed budget.

    Returns:
        Dict with default budgets and optional overage detection.
    """
    from ast_tools.agent_integration.token_tracker import DEFAULT_BUDGETS, TokenTracker

    tool_name = args.get("tool_name", "")
    result_length = args.get("result_length", 0)

    response = {
        "default_budgets": dict(DEFAULT_BUDGETS),
        "default_budget": DEFAULT_BUDGETS.get("default", 1000),
    }

    if tool_name and result_length:
        tracker = TokenTracker()
        result_text = "x" * result_length
        overage = tracker.track(tool_name, result_text)
        response["check"] = overage

    return response


def _tool_validate_usage(args: dict[str, Any]) -> dict[str, Any]:
    """Validate an ast-tools tool call before sending it.

    Checks for common error patterns and provides usage guidance.

    Parameters:
        tool_name: Name of the tool to validate.
        query_or_result: Example query or expected result text to check.

    Returns:
        Dict with validation result and any corrections.
    """
    tool_name = args.get("tool_name", "")
    query_or_result = args.get("query_or_result", "")

    if not tool_name:
        return {
            "valid": False,
            "message": "tool_name is required.",
        }

    if query_or_result:
        correction = correct_tool_error(tool_name, query_or_result)
        if correction:
            return {
                "valid": False,
                "message": "Potential issue detected — see correction.",
                "correction": correction.get("context", ""),
            }

    return {
        "valid": True,
        "message": f"No known issues with '{tool_name}' usage.",
    }


def register_tools(register_tool_func: Callable[[str, Callable], None]) -> None:
    """Register context injection tools.

    Args:
        register_tool_func: Function to register a tool (name, handler)
    """
    register_tool_func("context_inject", _tool_context_inject)
    register_tool_func("context_status", _tool_context_status)
    register_tool_func("token_status", _tool_token_status)
    register_tool_func("validate_usage", _tool_validate_usage)


# Export for tool registry
__all__ = ["register_tools"]
