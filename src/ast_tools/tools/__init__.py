"""
AST-Tools: Tool implementations and registry.
"""

from collections.abc import Callable
from typing import Any

TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

# Minimal tool schemas for dynamic context injection
TOOL_SCHEMAS: dict[str, dict] = {}


def register_tool(name: str, handler: Callable[[dict[str, Any]], dict[str, Any]], schema: dict | None = None) -> None:
    """Register a tool handler with optional schema."""
    TOOL_REGISTRY[name] = handler
    if schema:
        TOOL_SCHEMAS[name] = schema


def get_tool_handler(name: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Get handler for a tool by name."""
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}")
    return TOOL_REGISTRY[name]


def get_tool_schema(name: str) -> dict | None:
    """Get minimal schema for a tool by name."""
    return TOOL_SCHEMAS.get(name)


def list_tool_names() -> list[str]:
    """Return list of all registered tool names."""
    return list(TOOL_REGISTRY.keys())


def find_similar_tool(name: str, max_results: int = 3) -> list[str]:
    """Find similar tool names for 'did you mean?' suggestions."""
    import difflib
    
    all_names = list(TOOL_REGISTRY.keys())
    return difflib.get_close_matches(name, all_names, n=max_results, cutoff=0.5)


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
from .file_related import _tool_file_related_suggest
from .knowledge_graph import kg_query, kg_shortest_path, kg_neighborhood
from .repo_skeleton import _tool_repo_skeleton
from .blast_radius_v2 import _tool_blast_radius_v2
from .class_hierarchy import _tool_class_hierarchy
from .transitive_analysis import _tool_transitive_dependents
from .search_symbols import _tool_search_symbols
from .semantic_search import _tool_semantic_search
from .structural_analysis import _ast_find_callees, _ast_find_callers, _tool_structural_analysis
from .ts_edit import _tool_ts_edit
from .watcher import _tool_reindex_path, _tool_watch_add, _tool_watch_status

# Core AST tools with schemas
register_tool("ast_generate_stub", _tool_ast_generate_stub, {
    "description": "Generate .pyi stub file or interface from Python source",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "Path to source file"},
            "include_private": {"type": "boolean", "description": "Include private members", "default": False},
            "include_docstrings": {"type": "boolean", "description": "Include docstrings", "default": True},
            "output_format": {"type": "string", "enum": ["stub", "interface"], "default": "stub"},
        },
        "required": ["file"],
    },
})

register_tool("ast_refactor_extract_interface", _tool_ast_refactor_extract_interface, {
    "description": "Extract interface (ABC/Protocol) from a class",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "Path to source file containing the class"},
            "class_name": {"type": "string", "description": "Name of the class"},
            "interface_name": {"type": "string", "description": "Name for new interface"},
            "interface_type": {"type": "string", "enum": ["abc", "protocol"], "default": "abc"},
            "output_file": {"type": "string", "description": "Output path for interface"},
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["file", "class_name"],
    },
})

register_tool("ast_grep", _tool_ast_grep, {
    "description": "Structural code search using AST patterns",
    "inputSchema": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "AST pattern (e.g., 'def $FUNC($$$ARGS)')"},
            "path": {"type": "string", "description": "File or directory to search", "default": "."},
            "lang": {"type": "string", "description": "Language: python, javascript, typescript, rust, go, java, c, cpp"},
            "limit": {"type": "integer", "description": "Max results", "default": 50, "maximum": 500},
            "count_only": {"type": "boolean", "default": False},
            "top_level": {"type": "boolean", "default": False},
        },
        "required": ["pattern"],
    },
})

register_tool("ast_edit", _tool_ast_edit, {
    "description": "Surgical AST-based code modification",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "Path to file to edit"},
            "operation": {"type": "string", "enum": ["replace_node", "insert_after", "insert_before", "remove_node", "rename_function", "add_parameter", "change_signature"]},
            "params": {"type": "object", "description": "Operation-specific parameters"},
            "dry_run": {"type": "boolean", "default": False},
        },
        "required": ["file", "operation", "params"],
    },
})

register_tool("ast_read", _tool_ast_read, {
    "description": "Structural context extraction from a source file",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "Path to source file"},
            "include_private": {"type": "boolean", "default": False},
            "include_imports": {"type": "boolean", "default": True},
            "filter_by_type": {"type": "array", "items": {"type": "string", "enum": ["ClassDef", "FunctionDef", "AsyncFunctionDef", "Assign", "Import", "ImportFrom"]}},
        },
        "required": ["file"],
    },
})

register_tool("ast_query", _tool_ast_query, {
    "description": "Smart router - auto-selects best tool for your query",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language query"},
            "cwd": {"type": "string", "description": "Project root"},
        },
        "required": ["query"],
    },
})

register_tool("ast_capsule", _tool_ast_capsule, {
    "description": "Export code as self-contained capsule with dependencies",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "Path to source file"},
            "symbol": {"type": "string", "description": "Symbol to extract"},
        },
        "required": ["file"],
    },
})

# Project intelligence tools
register_tool("codebase_summary", _tool_codebase_summary, {
    "description": "High-level architecture overview (<500 tokens)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "cwd": {"type": "string", "description": "Project root"},
        },
        "required": [],
    },
})

register_tool("project_info", _tool_project_info, {
    "description": "Project intelligence manifest",
    "inputSchema": {
        "type": "object",
        "properties": {
            "cwd": {"type": "string", "description": "Project root"},
            "full": {"type": "boolean", "description": "Full manifest vs summary", "default": False},
            "diff": {"type": "boolean", "description": "Include diff since last scan", "default": False},
        },
        "required": [],
    },
})

register_tool("repo_skeleton", _tool_repo_skeleton, {
    "description": "Generate intelligent project skeleton with type detection, key file identification, ASCII tree, and dependency graph",
    "inputSchema": {
        "type": "object",
        "properties": {
            "root_path": {"type": "string", "description": "Project root path"},
            "max_depth": {"type": "integer", "description": "Directory traversal depth", "default": 5},
            "include_tests": {"type": "boolean", "description": "Include test files", "default": True},
            "include_configs": {"type": "boolean", "description": "Include config files", "default": True},
            "generate_deps": {"type": "boolean", "description": "Parse dependency files", "default": True},
        },
        "required": ["root_path"],
    },
})
register_tool("file_related_suggest", _tool_file_related_suggest, {
    "description": "Suggest files related to a given file based on imports, test patterns, and directory structure",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file to find related files for"},
            "workspace": {"type": "string", "description": "Project root directory (optional, auto-detects)"},
            "max_suggestions": {"type": "integer", "default": 5, "description": "Max number of suggestions"},
            "include_tests": {"type": "boolean", "default": True, "description": "Include test file suggestions"},
            "include_imports": {"type": "boolean", "default": True, "description": "Include import-based suggestions"},
        },
        "required": ["file_path"],
    },
})
register_tool("kg_query", kg_query, {
    "description": "Natural language knowledge graph query — find related symbols via graph traversal",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language query"},
            "max_depth": {"type": "integer", "default": 2},
            "max_nodes": {"type": "integer", "default": 50},
            "db_path": {"type": "string", "description": "Database override path"},
        },
        "required": ["query"],
    },
})
register_tool("kg_shortest_path", kg_shortest_path, {
    "description": "Find shortest path between two symbols via graph traversal",
    "inputSchema": {
        "type": "object",
        "properties": {
            "from_symbol": {"type": "string", "description": "Starting symbol name"},
            "to_symbol": {"type": "string", "description": "Target symbol name"},
            "max_depth": {"type": "integer", "default": 10},
            "db_path": {"type": "string"},
        },
        "required": ["from_symbol", "to_symbol"],
    },
})
register_tool("kg_neighborhood", kg_neighborhood, {
    "description": "Get all symbols related to a given symbol within N hops",
    "inputSchema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol name or query"},
            "max_depth": {"type": "integer", "default": 2},
            "max_nodes": {"type": "integer", "default": 50},
            "db_path": {"type": "string"},
        },
        "required": ["symbol"],
    },
})

# Structural analysis tools
register_tool("structural_analysis", _tool_structural_analysis, {
    "description": "Call graphs, type hierarchies, symbol references, dependency mapping",
    "inputSchema": {
        "type": "object",
        "properties": {
            "analysis_type": {"type": "string", "enum": ["callers", "callees", "type_hierarchy", "references", "dependencies"]},
            "symbol": {"type": "string", "description": "Symbol name to analyze"},
            "file": {"type": "string", "description": "File containing symbol"},
            "line": {"type": "integer", "description": "Line number of symbol"},
            "project_root": {"type": "string", "description": "Project root"},
        },
        "required": ["analysis_type"],
    },
})

register_tool("find_references", _tool_find_references, {
    "description": "Find all references to a symbol across the codebase",
    "inputSchema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol name to search for"},
            "cwd": {"type": "string", "description": "Project root"},
            "file": {"type": "string", "description": "Optional: narrow to specific file"},
            "limit": {"type": "integer", "default": 100},
        },
        "required": ["symbol"],
    },
})

register_tool("impact_analysis", _tool_impact_analysis, {
    "description": "Analyze impact of changing a file or symbol",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "File path or symbol name"},
            "cwd": {"type": "string", "description": "Project root"},
        },
        "required": ["target"],
    },
})

register_tool("transitive_dependents", _tool_transitive_dependents, {
    "description": "Find all files transitively affected by changes — the 'what breaks?' query. Builds a live import graph and BFS-traverses to find full dependency chain.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "File path or dotted module path"},
            "direction": {"type": "string", "enum": ["dependents", "dependencies"], "default": "dependents"},
            "max_depth": {"type": "integer", "default": 10, "description": "BFS depth limit"},
            "cwd": {"type": "string", "description": "Working directory for relative paths"},
        },
        "required": ["target"],
    },
})

register_tool("class_hierarchy", _tool_class_hierarchy, {
    "description": "Analyze class hierarchy — MRO, bases, subclasses, method categories, interface detection",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Class name, optionally prefixed as 'file.py:ClassName'"},
            "file": {"type": "string", "description": "File containing the class (optional, auto-detects from target)"},
            "workspace": {"type": "string", "description": "Project root (optional, auto-detects from file)"},
            "max_depth": {"type": "integer", "default": 10, "description": "MRO and subclass depth limit"},
        },
        "required": ["target"],
    },
})

register_tool("blast_radius_v2", _tool_blast_radius_v2, {
    "description": "Unified blast radius analysis across import graph + class hierarchy + call graph with confidence scoring",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "File path, class name, function name, or dotted module path"},
            "cwd": {"type": "string", "description": "Project root (optional, auto-detects)"},
            "max_depth": {"type": "integer", "default": 5, "description": "BFS depth for import graph"},
            "include_imports": {"type": "boolean", "default": True, "description": "Include import graph axis"},
            "include_hierarchy": {"type": "boolean", "default": True, "description": "Include class hierarchy axis"},
            "include_callers": {"type": "boolean", "default": True, "description": "Include call graph axis"},
        },
        "required": ["target"],
    },
})

register_tool("module_imports", _tool_module_imports, {
    "description": "Module-level import analysis (fan-in/fan-out)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "module": {"type": "string", "description": "Module path or file path"},
            "cwd": {"type": "string", "description": "Project root"},
            "max_files": {"type": "integer", "default": 500},
        },
        "required": ["module"],
    },
})

# Symbol search tools (require index)
register_tool("search_symbols", _tool_search_symbols, {
    "description": "Full-text symbol search (FTS5)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query (FTS5 syntax)"},
            "kind_filter": {"type": "array", "items": {"type": "string"}, "description": "Symbol kinds to filter"},
            "limit": {"type": "integer", "default": 50},
        },
        "required": ["query"],
    },
})

register_tool("find_symbol_definition", _tool_find_symbol_definition, {
    "description": "Find symbol by qualified name",
    "inputSchema": {
        "type": "object",
        "properties": {
            "qualified_name": {"type": "string", "description": "Fully qualified symbol name"},
        },
        "required": ["qualified_name"],
    },
})

register_tool("list_symbols", _tool_list_symbols, {
    "description": "List all symbols in a file",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to source file"},
        },
        "required": ["file_path"],
    },
})

# Index management
register_tool("index_status", _tool_index_status, {
    "description": "Get index statistics",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
})

register_tool("refresh_index", _tool_refresh_index, {
    "description": "Index/re-index a project",
    "inputSchema": {
        "type": "object",
        "properties": {
            "project_path": {"type": "string", "description": "Project root"},
            "force": {"type": "boolean", "description": "Re-index all files", "default": False},
            "embeddings": {"type": "boolean", "description": "Generate vector embeddings", "default": False},
        },
        "required": ["project_path"],
    },
})

register_tool("semantic_search", _tool_semantic_search, {
    "description": "Hybrid vector + FTS5 semantic search with auto context injection",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query"},
            "k": {"type": "integer", "description": "Number of results", "default": 10},
            "inject_context": {"type": "boolean", "description": "Inject formatted context", "default": True},
            "token_budget": {"type": "integer", "description": "Token budget for context", "default": 4096},
            "diversity_limit": {"type": "integer", "description": "Max symbols per file", "default": 3},
        },
        "required": ["query"],
    },
})

# Watcher tools
register_tool("watch_add", _tool_watch_add, {
    "description": "Add file watcher for auto-reindex",
    "inputSchema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to watch"},
        },
        "required": ["path"],
    },
})

register_tool("watch_status", _tool_watch_status, {
    "description": "Watch status",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
})

register_tool("reindex_path", _tool_reindex_path, {
    "description": "Re-index specific path",
    "inputSchema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to re-index"},
        },
        "required": ["path"],
    },
})

# Dependency graph tools
register_tool("circular_dependencies", _tool_circular_dependencies, {
    "description": "Detect circular imports",
    "inputSchema": {
        "type": "object",
        "properties": {
            "project_root": {"type": "string", "description": "Project root"},
        },
        "required": ["project_root"],
    },
})

register_tool("external_dependencies", _tool_external_dependencies, {
    "description": "Find third-party imports",
    "inputSchema": {
        "type": "object",
        "properties": {
            "project_root": {"type": "string", "description": "Project root"},
        },
        "required": ["project_root"],
    },
})

register_tool("dead_code_detection", _tool_dead_code_detection, {
    "description": "Basic dead code detection",
    "inputSchema": {
        "type": "object",
        "properties": {
            "project_root": {"type": "string", "description": "Project root"},
        },
        "required": ["project_root"],
    },
})

register_tool("dead_code_enhanced", _tool_dead_code_enhanced, {
    "description": "Enhanced dead code detection with confidence scoring",
    "inputSchema": {
        "type": "object",
        "properties": {
            "project_root": {"type": "string", "description": "Project root"},
        },
        "required": ["project_root"],
    },
})

register_tool("dependency_chain", _tool_dependency_chain, {
    "description": "Full dependency chain for a symbol",
    "inputSchema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol name"},
            "file": {"type": "string", "description": "File containing symbol"},
            "project_root": {"type": "string", "description": "Project root"},
        },
        "required": ["symbol", "file", "project_root"],
    },
})

register_tool("api_surface_diff", _tool_api_surface_diff, {
    "description": "Compare API surfaces between versions",
    "inputSchema": {
        "type": "object",
        "properties": {
            "old_path": {"type": "string", "description": "Old version path"},
            "new_path": {"type": "string", "description": "New version path"},
        },
        "required": ["old_path", "new_path"],
    },
})

# Curator tools
register_tool("curator_audit", _tool_curator_audit, {
    "description": "Automated code review",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "File or directory to audit"},
        },
        "required": ["target"],
    },
})

register_tool("curator_summary", _tool_curator_summary, {
    "description": "Curator review summary",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
})

register_tool("curator_status", _tool_curator_status, {
    "description": "Curator status",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
})

# Code validation
register_tool("code_validate_syntax", _tool_code_validate, {
    "description": "Syntax validation for 10+ languages",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "File to validate"},
            "lang": {"type": "string", "description": "Language (auto-detected)"},
        },
        "required": ["file"],
    },
})

# LSP tools
register_lsp_tools(TOOL_REGISTRY)

# Register LSP tool schemas
register_tool("lsp_available_languages", lambda x: x, {
    "description": "Get supported LSP languages and requirements",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
})

register_tool("lsp_check_server", lambda x: x, {
    "description": "Check if LSP server is installed for a language",
    "inputSchema": {
        "type": "object",
        "properties": {
            "lang": {"type": "string", "description": "Language (python, rust, go, etc.)"},
        },
        "required": ["lang"],
    },
})

register_tool("lsp_definition", lambda x: x, {
    "description": "Go to definition of symbol at position (LSP)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "File path"},
            "line": {"type": "integer", "description": "Line number (1-indexed)"},
            "col": {"type": "integer", "description": "Column (0-indexed)"},
        },
        "required": ["file", "line", "col"],
    },
})

register_tool("lsp_references", lambda x: x, {
    "description": "Find all references to symbol at position (LSP)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "line": {"type": "integer"},
            "col": {"type": "integer"},
        },
        "required": ["file", "line", "col"],
    },
})

register_tool("lsp_hover", lambda x: x, {
    "description": "Get type signature and documentation (LSP)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "line": {"type": "integer"},
            "col": {"type": "integer"},
        },
        "required": ["file", "line", "col"],
    },
})

register_tool("lsp_symbols", lambda x: x, {
    "description": "Get all symbols in a file (LSP)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
        },
        "required": ["file"],
    },
})

register_tool("lsp_call_hierarchy_in", lambda x: x, {
    "description": "Find callers of function (LSP call hierarchy)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "line": {"type": "integer"},
            "col": {"type": "integer"},
        },
        "required": ["file", "line", "col"],
    },
})

register_tool("lsp_call_hierarchy_out", lambda x: x, {
    "description": "Find functions called by function (LSP)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "line": {"type": "integer"},
            "col": {"type": "integer"},
        },
        "required": ["file", "line", "col"],
    },
})

# Context injection tools
from .context_tools import register_tools as register_context_tools

register_context_tools(register_tool)

# Register context tool schemas
register_tool("context_inject", lambda x: x, {
    "description": "Inject relevant context based on query and current file",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "current_file": {"type": "string", "description": "Current file context"},
            "max_symbols": {"type": "integer", "description": "Max symbols to return", "default": 10},
        },
        "required": ["query"],
    },
})

register_tool("context_status", lambda x: x, {
    "description": "Get context injection system status",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
})
# TypeScript editing
register_tool("ts_edit", _tool_ts_edit, {
    "description": "TypeScript/JavaScript structural editing",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file": {"type": "string", "description": "File to edit"},
            "operation": {"type": "string", "description": "Edit operation"},
            "params": {"type": "object", "description": "Operation parameters"},
        },
        "required": ["file", "operation", "params"],
    },
})

# Co-change analysis tools
from .co_change import (
    co_change_diff,
    co_change_history,
    co_change_hotspots,
    co_change_predict,
)

register_tool("co_change_predict", co_change_predict, {
    "description": "Given a file or symbol, return files that tend to change with it",
    "inputSchema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Symbol name or file path"},
            "top_n": {"type": "integer", "default": 10},
            "db_path": {"type": "string", "description": "Override DB path"},
        },
        "required": ["symbol"],
    },
})
register_tool("co_change_hotspots", co_change_hotspots, {
    "description": "Find top-N riskiest files by churn × coupling score",
    "inputSchema": {
        "type": "object",
        "properties": {
            "top_n": {"type": "integer", "default": 10},
            "db_path": {"type": "string"},
        },
        "required": [],
    },
})
register_tool("co_change_history", co_change_history, {
    "description": "Get churn/change history for a specific file",
    "inputSchema": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file"},
            "db_path": {"type": "string"},
        },
        "required": ["file_path"],
    },
})
register_tool("co_change_diff", co_change_diff, {
    "description": "Identify symbols at risk when changing this symbol",
    "inputSchema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "The symbol being changed"},
            "db_path": {"type": "string"},
        },
        "required": ["symbol"],
    },
})