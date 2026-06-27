"""Context injection MCP tools for ast-tools.

Provides MCP tools for manual context injection and configuration.
"""

from collections.abc import Callable
from typing import Any


def _tool_context_inject(args: dict[str, Any]) -> dict[str, Any]:
    """Inject relevant context based on query and current file."""
    query = args.get("query", "")
    current_file = args.get("current_file")
    args.get("max_symbols", 10)

    # This is a placeholder - full implementation needs database connection
    return {
        "status": "placeholder",
        "message": f"Context injection requested for query: '{query}' (file: {current_file or 'none'})",
    }


def _tool_context_status(args: dict[str, Any]) -> dict[str, Any]:
    """Get context injection system status."""
    return {
        "status": "available",
        "message": "Context injection system ready (needs database connection for full functionality)",
    }


def register_tools(register_tool_func: Callable[[str, Callable], None]) -> None:
    """Register context injection tools.

    Args:
        register_tool_func: Function to register a tool (name, handler)
    """
    register_tool_func("context_inject", _tool_context_inject)
    register_tool_func("context_status", _tool_context_status)


# Export for tool registry
__all__ = ["register_tools"]
