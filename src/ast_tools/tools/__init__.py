"""AST-Tools: Tool implementations and registry."""

from typing import Any, Callable

TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def register_tool(name: str, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    """Register a tool handler."""
    TOOL_REGISTRY[name] = handler


def get_tool_handler(name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Get handler for a tool by name."""
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}")
    return TOOL_REGISTRY[name]


def list_tool_names() -> list[str]:
    """Return list of all registered tool names."""
    return list(TOOL_REGISTRY.keys())


# Import and register all tools
from .ast_generate_stub import _tool_ast_generate_stub
from .ast_refactor_extract_interface import _tool_ast_refactor_extract_interface
from .codebase_summary import _tool_codebase_summary
from .project_info import _tool_project_info

register_tool("ast_generate_stub", _tool_ast_generate_stub)
register_tool("ast_refactor_extract_interface", _tool_ast_refactor_extract_interface)
register_tool("codebase_summary", _tool_codebase_summary)
register_tool("project_info", _tool_project_info)