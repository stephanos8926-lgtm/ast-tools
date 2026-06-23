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
from .ast_grep import _tool_ast_grep
from .ast_edit import _tool_ast_edit
from .ast_read import _tool_ast_read
from .codebase_summary import _tool_codebase_summary
from .project_info import _tool_project_info
from .structural_analysis import _tool_structural_analysis
from .find_references import _tool_find_references
from .impact_analysis import _tool_impact_analysis
from .module_imports import _tool_module_imports

register_tool("ast_generate_stub", _tool_ast_generate_stub)
register_tool("ast_refactor_extract_interface", _tool_ast_refactor_extract_interface)
register_tool("ast_grep", _tool_ast_grep)
register_tool("ast_edit", _tool_ast_edit)
register_tool("ast_read", _tool_ast_read)
register_tool("codebase_summary", _tool_codebase_summary)
register_tool("project_info", _tool_project_info)
register_tool("structural_analysis", _tool_structural_analysis)
register_tool("find_references", _tool_find_references)
register_tool("impact_analysis", _tool_impact_analysis)
register_tool("module_imports", _tool_module_imports)