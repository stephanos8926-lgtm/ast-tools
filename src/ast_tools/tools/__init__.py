"""AST-Tools: Tool implementations and registry."""

from collections.abc import Callable
from typing import Any

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


# Import and register all tools (imports after code is intentional for tool registration)
# ruff: noqa: E402
from .ast_capsule import _tool_ast_capsule
from .ast_edit import _tool_ast_edit
from .ast_generate_stub import _tool_ast_generate_stub
from .ast_grep import _tool_ast_grep
from .ast_query import _tool_ast_query
from .ast_read import _tool_ast_read
from .ast_refactor_extract_interface import _tool_ast_refactor_extract_interface
from .code_validate import _tool_code_validate
from .codebase_summary import _tool_codebase_summary
from .curator import _tool_curator_audit, _tool_curator_status, _tool_curator_summary
from .dependency_tools import (
    _tool_api_surface_diff,
    _tool_circular_dependencies,
    _tool_dead_code_detection,
    _tool_dependency_chain,
    _tool_external_dependencies,
)
from .enhanced_dead_code import _tool_dead_code_enhanced
from .find_references import _tool_find_references
from .find_symbol_definition import _tool_find_symbol_definition
from .impact_analysis import _tool_impact_analysis
from .index_status import _tool_index_status
from .list_symbols import _tool_list_symbols
from .lsp_tools import register_lsp_tools
from .module_imports import _tool_module_imports
from .project_info import _tool_project_info
from .refresh_index import _tool_refresh_index
from .search_symbols import _tool_search_symbols
from .semantic_search import _tool_semantic_search
from .structural_analysis import _ast_find_callers, _ast_find_callees
from .ts_edit import _tool_ts_edit
from .watcher import _tool_reindex_path, _tool_watch_add, _tool_watch_status

register_tool("ast_generate_stub", _tool_ast_generate_stub)
register_tool("ast_refactor_extract_interface", _tool_ast_refactor_extract_interface)
register_tool("ast_grep", _tool_ast_grep)
register_tool("ast_edit", _tool_ast_edit)
register_tool("ast_read", _tool_ast_read)
register_tool("ast_query", _tool_ast_query)  # Smart router
register_tool("ast_capsule", _tool_ast_capsule)  # Consolidated view
register_tool("codebase_summary", _tool_codebase_summary)
register_tool("project_info", _tool_project_info)
register_tool("structural_analysis", _tool_structural_analysis)
register_tool("find_references", _tool_find_references)
register_tool("impact_analysis", _tool_impact_analysis)
register_tool("module_imports", _tool_module_imports)
register_tool("search_symbols", _tool_search_symbols)
register_tool("find_symbol_definition", _tool_find_symbol_definition)
register_tool("list_symbols", _tool_list_symbols)
register_tool("index_status", _tool_index_status)
register_tool("refresh_index", _tool_refresh_index)
register_tool("semantic_search", _tool_semantic_search)
register_tool("watch_add", _tool_watch_add)
register_tool("watch_status", _tool_watch_status)
register_tool("reindex_path", _tool_reindex_path)

# Register dependency graph tools
register_tool("circular_dependencies", _tool_circular_dependencies)
register_tool("external_dependencies", _tool_external_dependencies)
register_tool("dead_code_detection", _tool_dead_code_detection)
register_tool("dead_code_enhanced", _tool_dead_code_enhanced)
register_tool("dependency_chain", _tool_dependency_chain)
register_tool("api_surface_diff", _tool_api_surface_diff)

# Register curator tools
register_tool("curator_audit", _tool_curator_audit)
register_tool("curator_summary", _tool_curator_summary)
register_tool("curator_status", _tool_curator_status)

# Register code validation tool
register_tool("code_validate_syntax", _tool_code_validate)

# Register LSP tools
register_lsp_tools(TOOL_REGISTRY)

# Register context injection tools
from .context_tools import register_tools as register_context_tools

register_context_tools(register_tool)

# Register TypeScript editing tool
register_tool("ts_edit", _tool_ts_edit)
