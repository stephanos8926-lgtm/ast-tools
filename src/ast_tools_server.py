#!/usr/bin/env python3
"""
AST Tools MCP Server — structural code analysis and editing tools.

Exposes 17 tools:
  ast_grep                    — Structural search (via ast-grep CLI)
  ast_edit                    — Surgical AST-based modification (via libcst)
  ast_read                    — Structural context extraction (via ast module)
  ast_generate_stub           — Generate .pyi stubs or interfaces (via ast)
  ast_refactor_extract_interface — Extract interface to ABC/Protocol (via libcst)
  structural_analysis         — Call graphs, type hierarchies, symbol references (via jedi)
  project_info                — Project intelligence (project.json manifest)
  codebase_summary            — High-level architecture overview (<500 tokens)
  find_references             — Cross-file symbol usage search
  impact_analysis             — What breaks if you change a file or symbol
  module_imports              — Module-level import analysis (fan-in / fan-out)
  search_symbols              — FTS5 full-text search of indexed symbols
  find_symbol_definition      — Find symbol by qualified name
  list_symbols                — List symbols in a file
  index_status                — Get index statistics
  refresh_index               — Index a project (incremental, with content hashing)
  semantic_search             — Hybrid vector + FTS5 semantic search
"""

import json
import logging
import sys
from typing import Any

import anyio
from mcp.server import Server
from mcp.types import TextContent, Tool

from ast_tools.tools import TOOL_REGISTRY, get_tool_handler, list_tool_names

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger(__name__)

server = Server("ast-tools")


# ─── Tool Definitions ────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ast_grep",
            description=(
                "Structural code search using AST patterns. "
                "Finds code structures regardless of whitespace, comments, or naming. "
                "Supports Python, JavaScript, TypeScript, Rust, Go, Java, C, C++, and more. "
                "Examples: 'def $FUNC($$$ARGS)' matches any function definition, "
                "'call($OBJ, $METHOD)' matches any method call with 2 args."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "AST pattern to search for. Use $VAR for single nodes, $$$VAR for multiple.",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search in. Defaults to current directory.",
                    },
                    "lang": {
                        "type": "string",
                        "description": "Language to parse as. One of: python, javascript, typescript, rust, go, java, c, cpp. Auto-detected from file extension if not specified.",
                    },
                    "json_output": {
                        "type": "boolean",
                        "description": "Return results as JSON with file, line, column, text. Default: true.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of matches to return. Default: 50, max: 500.",
                    },
                    "count_only": {
                        "type": "boolean",
                        "description": "If true, return only the count (no match data). Default: false.",
                    },
                    "top_level": {
                        "type": "boolean",
                        "description": "If true, only match top-level function/class definitions (not methods inside classes). Default: false.",
                    },
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="ast_edit",
            description=(
                "Surgical AST-based code modification. "
                "Performs precise structural edits that preserve formatting and comments. "
                "Uses libcst (Concrete Syntax Tree) for lossless transformations. "
                "Operations: replace_node, insert_after, insert_before, remove_node, "
                "rename_function, add_parameter, change_signature."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path to the file to edit.",
                    },
                    "operation": {
                        "type": "string",
                        "description": "Edit operation to perform.",
                        "enum": [
                            "replace_node",
                            "insert_after",
                            "insert_before",
                            "remove_node",
                            "rename_function",
                            "add_parameter",
                            "change_signature",
                        ],
                    },
                    "params": {
                        "type": "object",
                        "description": "Operation-specific parameters as a JSON object.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, return the modified source without writing. Default: false.",
                    },
                },
                "required": ["file", "operation", "params"],
            },
        ),
        Tool(
            name="ast_read",
            description=(
                "Structural context extraction from a source file. "
                "Returns the high-level API surface: classes, functions, imports, and variables "
                "with their signatures, line numbers, and docstrings — without reading every line."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path to the source file.",
                    },
                    "include_private": {
                        "type": "boolean",
                        "description": "Include private members (prefixed with _). Default: false.",
                    },
                    "include_imports": {
                        "type": "boolean",
                        "description": "Include import statements. Default: true.",
                    },
                    "filter_by_type": {
                        "type": "array",
                        "description": "Filter results to only include specific AST node types. Valid values: 'ClassDef', 'FunctionDef', 'AsyncFunctionDef', 'Assign', 'Import', 'ImportFrom'. Default: include all.",
                        "items": {
                            "type": "string",
                            "enum": ["ClassDef", "FunctionDef", "AsyncFunctionDef", "Assign", "Import", "ImportFrom"]
                        },
                    },
                },
                "required": ["file"],
            },
        ),
        Tool(
            name="ast_generate_stub",
            description=(
                "Generate a .pyi stub file (type hints only) or interface file from a Python source file. "
                "Extracts function/method signatures, class definitions, and docstrings while omitting "
                "implementation details. Useful for creating API documentation, interface definitions, "
                "or type stubs for static analysis."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path to the source file.",
                    },
                    "include_private": {
                        "type": "boolean",
                        "description": "Include private members (prefixed with _). Default: false.",
                    },
                    "include_docstrings": {
                        "type": "boolean",
                        "description": "Include docstrings in the stub. Default: true.",
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output format: 'stub' for .pyi stub file, 'interface' for interface-only summary. Default: 'stub'.",
                        "enum": ["stub", "interface"],
                    },
                },
                "required": ["file"],
            },
        ),
        Tool(
            name="ast_refactor_extract_interface",
            description=(
                "Extract a public interface from a class and create an Abstract Base Class (ABC) or Protocol. "
                "Analyzes the target class, identifies its public methods and properties, generates a new "
                "interface file (ABC or Protocol), and modifies the original class to inherit from/implement "
                "the new interface. Useful for enforcing architectural boundaries, enabling dependency inversion, "
                "and preparing for component-based refactoring."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path to the source file containing the class.",
                    },
                    "class_name": {
                        "type": "string",
                        "description": "Name of the class to extract interface from.",
                    },
                    "interface_name": {
                        "type": "string",
                        "description": "Name for the new interface (e.g., 'IMyClass' or 'MyClassProtocol'). Default: 'I' + class_name.",
                    },
                    "interface_type": {
                        "type": "string",
                        "description": "Type of interface to generate: 'abc' for Abstract Base Class with abstractmethods, 'protocol' for typing.Protocol. Default: 'abc'.",
                        "enum": ["abc", "protocol"],
                    },
                    "output_file": {
                        "type": "string",
                        "description": "Path for the new interface file. Default: same directory as source with interface_name.py.",
                    },
                    "include_properties": {
                        "type": "boolean",
                        "description": "Include @property methods in the interface. Default: true.",
                    },
                    "include_classmethods": {
                        "type": "boolean",
                        "description": "Include @classmethod methods in the interface. Default: true.",
                    },
                    "include_staticmethods": {
                        "type": "boolean",
                        "description": "Include @staticmethod methods in the interface. Default: true.",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, return the generated files without writing. Default: false.",
                    },
                },
                "required": ["file", "class_name"],
            },
        ),
        Tool(
            name="structural_analysis",
            description=(
                "Multi-hop structural analysis of Python code. "
                "Capabilities: call graphs (who calls X / what does X call), "
                "type hierarchies (class inheritance), "
                "symbol references (every use of a name across the project), "
                "dependency mapping (module import graph)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis_type": {
                        "type": "string",
                        "description": "Type of analysis to perform.",
                        "enum": [
                            "callers",
                            "callees",
                            "type_hierarchy",
                            "references",
                            "dependencies",
                        ],
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to analyze (function, class, or variable name).",
                    },
                    "file": {
                        "type": "string",
                        "description": "File containing the symbol. Required for callers/callees/references.",
                    },
                    "line": {
                        "type": "integer",
                        "description": "Line number of the symbol definition. Required for callers/callees/references.",
                    },
                    "project_root": {
                        "type": "string",
                        "description": "Project root directory for cross-file analysis. Defaults to the file's parent directory.",
                    },
                },
                "required": ["analysis_type"],
            },
        ),
        Tool(
            name="project_info",
            description=(
                "Project intelligence — returns a structured manifest of the project "
                "at the given path. Reads project.json if it exists, or auto-generates "
                "one by scanning the codebase. Includes: name, version, languages, "
                "entry points, test framework, module structure, symbol index."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "cwd": {
                        "type": "string",
                        "description": "Project root directory. Defaults to current directory.",
                    },
                    "full": {
                        "type": "boolean",
                        "description": "If true, return the complete JSON manifest. Default: false (summary mode, <500 tokens).",
                    },
                    "diff": {
                        "type": "boolean",
                        "description": "If true, include added/removed/modified symbols since last scan. Default: false.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="codebase_summary",
            description=(
                "High-level architecture overview of a codebase. "
                "Returns a compact markdown-like summary with: project name, languages, "
                "module count, symbol count, entry points, test framework, "
                "top modules, and dependency hotspots. "
                "Optimized for LLM context — under 500 tokens."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "cwd": {
                        "type": "string",
                        "description": "Project root directory. Defaults to current directory.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="find_references",
            description=(
                "Find all references to a symbol across the codebase. "
                "Searches all Python files for ast.Name nodes matching the symbol. "
                "Returns file, line, column, and context for each occurrence. "
                "Groups results by file, sorted by line number."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol name to search for (function, class, or variable name).",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Project root directory. Defaults to current directory.",
                    },
                    "file": {
                        "type": "string",
                        "description": "Optional: narrow search to a specific file.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return. Default: 100.",
                    },
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="impact_analysis",
            description=(
                "Analyze the impact of changing a file or symbol. "
                "Returns: direct dependents (files that import/call the target), "
                "transitive dependents (files that depend on dependents), "
                "test files that exercise the target, "
                "and risk assessment (low/medium/high based on fan-out)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "File path or symbol name to analyze.",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Project root directory. Defaults to current directory.",
                    },
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="module_imports",
            description=(
                "Module-level import analysis — shows fan-in (what imports FROM this module) "
                "and fan-out (what this module imports FROM). "
                "Use BEFORE refactoring to understand dependencies and avoid circular imports. "
                "Returns: fan_in (modules that import from target), fan_out (modules target imports from), "
                "circular_deps (modules with mutual imports), and detailed import_lines."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "module": {
                        "type": "string",
                        "description": "Module path like 'nexusagent.core.worker' or file path like 'src/nexusagent/core/worker.py'.",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Project root directory. Defaults to current directory.",
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Max files to scan. Default: 500.",
                    },
                },
                "required": ["module"],
            },
        ),
        Tool(
            name="search_symbols",
            description=(
                "Search indexed symbols using full-text search (FTS5). "
                "Supports keywords, phrases, and boolean operators (OR, AND, NOT). "
                "Requires index to be initialized via refresh_index first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (FTS5 syntax: keywords, phrases, OR/AND/NOT)",
                    },
                    "kind_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional symbol kinds to filter (function, class, method, variable, import, constant)",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 50,
                        "description": "Maximum results to return",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="find_symbol_definition",
            description=(
                "Find a symbol definition by its qualified name. "
                "Returns symbol details including file location, line numbers, signature, and docstring. "
                "Requires index to be initialized via refresh_index first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "qualified_name": {
                        "type": "string",
                        "description": "Fully qualified symbol name (e.g., 'module.Class.method')",
                    },
                },
                "required": ["qualified_name"],
            },
        ),
        Tool(
            name="list_symbols",
            description=(
                "List all symbols in a specific file. "
                "Returns symbols with name, kind, line numbers, and signatures. "
                "Requires index to be initialized via refresh_index first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the source file",
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="index_status",
            description=(
                "Get statistics about the semantic index. "
                "Returns: indexed_files, total_symbols, total_edges, last_update, symbols_by_kind. "
                "Use to check if indexing is complete and up to date."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="refresh_index",
            description=(
                "Refresh the semantic index for a project. "
                "Scans all Python files, extracts symbols and edges, updates the database. "
                "Uses content hashing to skip unchanged files (incremental indexing). "
                "Use force=True to re-index everything. "
                "Use embeddings=True to generate vector embeddings for semantic search."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project root",
                    },
                    "force": {
                        "type": "boolean",
                        "default": False,
                        "description": "If True, re-index all files even if unchanged",
                    },
                    "embeddings": {
                        "type": "boolean",
                        "default": False,
                        "description": "If True, generate vector embeddings for all symbols (requires sentence-transformers)",
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="semantic_search",
            description=(
                "Hybrid semantic + keyword search for code symbols. "
                "Combines vector similarity (meaning-based) with FTS5 full-text search (keyword-based) "
                "using Reciprocal Rank Fusion for best results. "
                "Finds code by intent (\"authentication logic\") not just by name (\"authenticate_user\"). "
                "Requires index initialized via refresh_index and embeddings generated (refresh_index --embeddings)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query (semantic meaning)",
                    },
                    "k": {
                        "type": "integer",
                        "default": 10,
                        "description": "Number of results to return",
                    },
                    "kind_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional symbol kinds to filter (function, class, method, variable, import, constant)",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


# ─── Tool Handlers ────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to registered handlers."""
    try:
        if name not in TOOL_REGISTRY:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}", "error_code": "NOT_FOUND", "available_tools": list_tool_names()}))]
        
        handler = get_tool_handler(name)
        result = await anyio.to_thread.run_sync(handler, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return [TextContent(type="text", text=json.dumps({"error": str(e), "error_code": "INTERNAL", "tool": name}))]
