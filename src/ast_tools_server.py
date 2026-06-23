#!/usr/bin/env python3
"""
AST Tools MCP Server — structural code analysis and editing tools.

Exposes 11 tools:
  ast_grep    — Structural search (via ast-grep CLI)
  ast_edit    — Surgical AST-based modification (via libcst)
  ast_read    — Structural context extraction (via ast module)
  ast_generate_stub — Generate .pyi stubs or interfaces (via ast)
  ast_refactor_extract_interface — Extract interface to ABC/Protocol (via libcst)
  structural_analysis — Call graphs, type hierarchies, symbol references (via jedi)
  project_info — Project intelligence (project.json manifest)
  codebase_summary — High-level architecture overview (<500 tokens)
  find_references — Cross-file symbol usage search
  impact_analysis — What breaks if you change a file or symbol
  module_imports — Module-level import analysis (fan-in / fan-out)
"""

import ast
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import anyio
import libcst as cst
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ast_tools.tools import TOOL_REGISTRY, get_tool_handler, list_tool_names
from ast_tools.utils import (
    _annotation_to_str,
    _extract_all_names,
    _get_function_signature,
    build_reverse_deps,
    classify_risk,
    file_to_module,
    filter_top_level,
    find_python_files,
    get_transitive_deps,
    is_test_file,
)

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
    ]


# ─── Tool Handlers ────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        # Check if tool is in registry (extracted tools)
        if name in TOOL_REGISTRY:
            handler = get_tool_handler(name)
            result = await anyio.to_thread.run_sync(handler, arguments)
        elif name == "ast_grep":
            result = await anyio.to_thread.run_sync(_tool_ast_grep, arguments)
        elif name == "ast_edit":
            result = await anyio.to_thread.run_sync(_tool_ast_edit, arguments)
        elif name == "ast_read":
            result = await anyio.to_thread.run_sync(_tool_ast_read, arguments)
        elif name == "structural_analysis":
            result = await anyio.to_thread.run_sync(_tool_structural_analysis, arguments)
        elif name == "find_references":
            result = await anyio.to_thread.run_sync(_tool_find_references, arguments)
        elif name == "impact_analysis":
            result = await anyio.to_thread.run_sync(_tool_impact_analysis, arguments)
        elif name == "module_imports":
            result = await anyio.to_thread.run_sync(_tool_module_imports, arguments)
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}", "error_code": "NOT_FOUND", "tools": "unknown"}))]
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return [TextContent(type="text", text=json.dumps({"error": str(e), "error_code": "INTERNAL", "tool": name}))]


# ─── ast_grep ─────────────────────────────────────────────────────────────

def _tool_ast_grep(args: dict[str, Any]) -> dict[str, Any]:
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
        return {"error": "ast-grep CLI not found. Install: cargo install ast-grep", "error_code": "NOT_FOUND", "tool": "ast_grep"}
    except subprocess.TimeoutExpired:
        return {"error": "ast-grep timed out after 30s", "error_code": "TIMEOUT", "tool": "ast_grep"}

    if proc.returncode != 0 and not proc.stdout:
        return {"error": proc.stderr.strip() or "ast-grep returned no output", "matches": [], "error_code": "PARSE_ERROR", "tool": "ast_grep"}

    if json_output:
        try:
            matches = json.loads(proc.stdout)
        except json.JSONDecodeError:
            matches = []
    else:
        lines = [l for l in proc.stdout.strip().splitlines() if l]
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


# ─── ast_grep ─────────────────────────────────────────────────────────────

# Replaced with import from utils: find_python_files, is_test_file, file_to_module


# ─── ast_edit ─────────────────────────────────────────────────────────────

def _tool_ast_edit(args: dict[str, Any]) -> dict[str, Any]:
    file_path = Path(args["file"]).resolve()
    operation = args["operation"]
    params = args.get("params", {})
    dry_run = args.get("dry_run", False)

    if not file_path.exists():
        return {"error": f"File not found: {file_path}", "error_code": "NOT_FOUND", "tool": "ast_edit"}

    source = file_path.read_text()
    try:
        tree = cst.parse_module(source)
    except cst.ParserSyntaxError as e:
        return {"error": f"Syntax error in {file_path}: {e}", "error_code": "PARSE_ERROR", "tool": "ast_edit"}

    transformer = _build_transformer(operation, params)
    if transformer is None:
        return {"error": f"Unknown operation: {operation}", "error_code": "INVALID_INPUT", "tool": "ast_edit"}

    import libcst.metadata as cst_meta
    wrapper = cst.MetadataWrapper(tree)
    try:
        new_tree = wrapper.visit(transformer)
    except Exception as e:
        return {"error": f"Transformation failed: {e}", "error_code": "INTERNAL", "tool": "ast_edit"}

    new_source = new_tree.code

    if dry_run:
        return {"file": str(file_path), "operation": operation, "modified_source": new_source}

    file_path.write_text(new_source)
    return {"file": str(file_path), "operation": operation, "status": "written"}


def _build_transformer(operation: str, params: dict):
    """Build a libcst transformer for the given operation."""

    if operation == "rename_function":
        old_name = params["old_name"]
        new_name = params["new_name"]

        class RenameTransformer(cst.CSTTransformer):
            def leave_FunctionDef(self, original_node, updated_node):
                if updated_node.name.value == old_name:
                    return updated_node.with_changes(name=cst.Name(new_name))
                return updated_node

            def leave_Call(self, original_node, updated_node):
                if isinstance(updated_node.func, cst.Name) and updated_node.func.value == old_name:
                    return updated_node.with_changes(func=cst.Name(new_name))
                return updated_node

        return RenameTransformer()

    elif operation == "add_parameter":
        func_name = params["function_name"]
        param_name = params["parameter_name"]
        default_value = params.get("default_value")

        class AddParamTransformer(cst.CSTTransformer):
            def leave_FunctionDef(self, original_node, updated_node):
                if updated_node.name.value == func_name:
                    default = cst.parse_expression(default_value) if default_value else None
                    new_param = cst.Param(
                        name=cst.Name(param_name),
                        default=default,
                    )
                    params_list = list(updated_node.params.params)
                    params_list.append(new_param)
                    return updated_node.with_changes(
                        params=updated_node.params.with_changes(params=params_list)
                    )
                return updated_node

        return AddParamTransformer()

    elif operation == "change_signature":
        func_name = params["function_name"]
        new_params = params["parameters"]  # list of {"name": str, "default": str|None}

        class ChangeSigTransformer(cst.CSTTransformer):
            def leave_FunctionDef(self, original_node, updated_node):
                if updated_node.name.value == func_name:
                    new_params_list = []
                    for p in new_params:
                        default = cst.parse_expression(p["default"]) if p.get("default") else None
                        new_params_list.append(cst.Param(name=cst.Name(p["name"]), default=default))
                    return updated_node.with_changes(
                        params=updated_node.params.with_changes(params=new_params_list)
                    )
                return updated_node

        return ChangeSigTransformer()

    elif operation == "replace_node":
        # Replace a specific AST node identified by line range
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        replacement = params["replacement"]

        class ReplaceTransformer(cst.CSTTransformer):
            METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

            def __init__(self):
                self._replacement_nodes = list(cst.parse_module(replacement).body)

            def leave_Module(self, original_node, updated_node):
                if start_line is None:
                    return updated_node
                new_body = []
                for stmt in updated_node.body:
                    try:
                        pos = self.get_metadata(cst.metadata.PositionProvider, stmt)
                        stmt_line = pos.start.line
                    except (KeyError, AttributeError):
                        stmt_line = 0
                    if start_line <= stmt_line <= end_line:
                        if not hasattr(self, '_replaced'):
                            new_body.extend(self._replacement_nodes)
                            self._replaced = True
                    else:
                        new_body.append(stmt)
                return updated_node.with_changes(body=new_body)

        return ReplaceTransformer()

    elif operation == "remove_node":
        start_line = params.get("start_line")
        end_line = params.get("end_line")

        class RemoveTransformer(cst.CSTTransformer):
            METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

            def leave_Module(self, original_node, updated_node):
                if start_line is None:
                    return updated_node
                new_body = []
                for stmt in updated_node.body:
                    try:
                        pos = self.get_metadata(cst.metadata.PositionProvider, stmt)
                        stmt_line = pos.start.line
                    except (KeyError, AttributeError):
                        stmt_line = 0
                    if start_line <= stmt_line <= end_line:
                        continue
                    new_body.append(stmt)
                return updated_node.with_changes(body=new_body)

        return RemoveTransformer()

    return None


# ─── ast_read ─────────────────────────────────────────────────────────────

def _extract_all_names(tree: ast.Module) -> list[str] | None:
    """Extract the list of names from an __all__ assignment if it exists.

    Handles: __all__ = ["Foo", "bar"]
    Returns the list of names, or None if __all__ is not defined.
    """
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if (isinstance(node.value, ast.List)
                            and all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                                   for e in node.value.elts)):
                        return [e.value for e in node.value.elts
                                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return None


def _tool_ast_read(args: dict[str, Any]) -> dict[str, Any]:
    file_path = Path(args["file"]).resolve()
    include_private = args.get("include_private", False)
    include_imports = args.get("include_imports", True)
    filter_by_type = args.get("filter_by_type", None)

    if not file_path.exists():
        return {"error": f"File not found: {file_path}", "error_code": "NOT_FOUND", "tool": "ast_read"}

    source = file_path.read_text()
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        return {"error": f"Syntax error: {e}", "error_code": "PARSE_ERROR", "tool": "ast_read"}

    result: dict[str, Any] = {
        "file": str(file_path),
        "language": "python",
    }

    # Helper to check if a type should be included
    def _should_include(node_type: str) -> bool:
        if filter_by_type is None:
            return True
        return node_type in filter_by_type

    if include_imports and _should_include("Import"):
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "module": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    })
            elif isinstance(node, ast.ImportFrom) and _should_include("ImportFrom"):
                imports.append({
                    "module": node.module,
                    "names": [a.name for a in node.names],
                    "aliases": {a.name: a.asname for a in node.names if a.asname},
                    "line": node.lineno,
                })
        result["imports"] = imports

    # Check for __all__ export list
    all_names = _extract_all_names(tree)
    filtered_by_all = all_names is not None
    if filtered_by_all:
        all_set = set(all_names)
    else:
        all_set = set()

    classes = []
    functions = []
    variables = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and _should_include("ClassDef"):
            if not include_private and node.name.startswith("_"):
                continue
            if filtered_by_all and node.name not in all_set:
                continue
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not include_private and item.name.startswith("_"):
                        continue
                    sig = _get_function_signature(item)
                    methods.append({
                        "name": item.name,
                        "signature": sig,
                        "line": item.lineno,
                        "end_line": item.end_lineno,
                        "docstring": ast.get_docstring(item),
                        "decorators": [ast.dump(d) for d in item.decorator_list],
                    })
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "end_line": node.end_lineno,
                "bases": [_annotation_to_str(b) for b in node.bases],
                "docstring": ast.get_docstring(node),
                "methods": methods,
                "decorators": [ast.dump(d) for d in node.decorator_list],
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node_type = "FunctionDef" if isinstance(node, ast.FunctionDef) else "AsyncFunctionDef"
            if _should_include(node_type):
                if not include_private and node.name.startswith("_"):
                    continue
                if filtered_by_all and node.name not in all_set:
                    continue
                sig = _get_function_signature(node)
                functions.append({
                    "name": node.name,
                    "signature": sig,
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                    "docstring": ast.get_docstring(node),
                    "decorators": [ast.dump(d) for d in node.decorator_list],
                })
        elif isinstance(node, ast.Assign) and _should_include("Assign"):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "__all__":
                        continue  # Skip __all__ assignment itself
                    if not include_private and target.id.startswith("_"):
                        continue
                    if filtered_by_all and target.id not in all_set:
                        continue
                    variables.append({
                        "name": target.id,
                        "line": node.lineno,
                        "value_preview": ast.dump(node.value)[:100],
                    })

    if _should_include("ClassDef"):
        result["classes"] = classes
    if _should_include("FunctionDef") or _should_include("AsyncFunctionDef"):
        result["functions"] = functions
    if _should_include("Assign"):
        result["variables"] = variables
    result["filtered_by__all__"] = filtered_by_all
    result["summary"] = {
        "total_classes": len(classes),
        "total_functions": len(functions),
        "total_variables": len(variables),
        "total_imports": len(result.get("imports", [])),
    }

    return result


def _annotation_to_str(node: ast.expr | None) -> str:
    """Convert an AST annotation node to a human-readable type string.

    Handles:
      ast.Name(id='str')                    -> "str"
      ast.Name(id='int')                    -> "int"
      ast.Constant(value=None)             -> "None"
      ast.Subscript(value=Name('list'), slice=Name('str')) -> "list[str]"
      ast.BinOp(left, op=BitOr(), right)   -> "X | Y"
      ast.Attribute(value=Name('pathlib'), attr='Path') -> "pathlib.Path"
    Fallback: ast.dump truncated to 80 chars.
    """
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.Attribute):
        value_str = _annotation_to_str(node.value)
        return f"{value_str}.{node.attr}" if value_str else node.attr
    if isinstance(node, ast.Subscript):
        value_str = _annotation_to_str(node.value)
        slice_str = _annotation_to_str(node.slice)
        return f"{value_str}[{slice_str}]"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left_str = _annotation_to_str(node.left)
        right_str = _annotation_to_str(node.right)
        return f"{left_str} | {right_str}"
    if isinstance(node, ast.Tuple):
        # Handle multi-element subscripts like Dict[str, int]
        elements = [_annotation_to_str(e) for e in node.elts]
        return ", ".join(elements)
    # Fallback: truncated ast.dump
    dumped = ast.dump(node)
    return dumped if len(dumped) <= 80 else dumped[:77] + "..."


def _get_function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Extract a human-readable function signature."""
    args = node.args
    parts = []

    # Positional args
    for arg in args.args:
        name = arg.arg
        if arg.annotation:
            name += f": {_annotation_to_str(arg.annotation)}"
        parts.append(name)

    # *args
    if args.vararg:
        vname = f"*{args.vararg.arg}"
        if args.vararg.annotation:
            vname += f": {_annotation_to_str(args.vararg.annotation)}"
        parts.append(vname)

    # Keyword-only
    for arg in args.kwonlyargs:
        name = arg.arg
        if arg.annotation:
            name += f": {_annotation_to_str(arg.annotation)}"
        parts.append(name)

    # **kwargs
    if args.kwarg:
        kname = f"**{args.kwarg.arg}"
        if args.kwarg.annotation:
            kname += f": {_annotation_to_str(args.kwarg.annotation)}"
        parts.append(kname)

    sig = f"({', '.join(parts)})"
    if node.returns:
        sig += f" -> {_annotation_to_str(node.returns)}"
    return sig


# ─── structural_analysis ─────────────────────────────────────────────────

# Backward-compat wrappers calling imported utils


def _find_python_files(project_root: str, max_files: int | None = None) -> list[Path]:
    """Wrapper calling find_python_files from utils."""
    return find_python_files(project_root, max_files=max_files)


def _is_test_file(file_path: str) -> bool:
    """Wrapper calling is_test_file from utils."""
    return is_test_file(file_path)


def _file_to_module(file_path: str, root: Path) -> str:
    """Wrapper calling file_to_module from utils."""
    return file_to_module(file_path, root)


def _build_reverse_deps(dep_graph: dict[str, list[str]]) -> dict[str, list[str]]:
    """Wrapper calling build_reverse_deps from utils."""
    return build_reverse_deps(dep_graph)


def _get_transitive_deps(
    target: str,
    reverse_deps: dict[str, list[str]],
    max_depth: int = 10,
) -> list[str]:
    """Wrapper - utils version is simpler, this keeps old BFS logic."""
    # Keep the existing BFS logic here since it's more complex than the simple version
    from collections import deque
    
    visited: set[str] = set()
    queue = deque(reverse_deps.get(target, []))
    for item in queue:
        visited.add(item)
    depth = 0
    while queue and depth < max_depth:
        next_queue: deque[str] = deque()
        for current in queue:
            for dep in reverse_deps.get(current, []):
                if dep not in visited:
                    visited.add(dep)
                    next_queue.append(dep)
        queue = next_queue
        depth += 1
    return sorted(visited)


def _classify_risk(fan_out: int) -> str:
    """Wrapper calling classify_risk from utils."""
    return classify_risk(fan_out)


def _ast_find_references(symbol: str, project_root: str) -> list[dict]:
    """Find all references to `symbol` across the project using AST.

    Walks all Python files, finds ast.Name nodes where node.id == symbol.
    Returns list of {file, line, col, context} grouped by file, sorted by line.
    """
    results = []
    for py_file in _find_python_files(project_root):
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            lines = source.splitlines()
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == symbol:
                line_num = node.lineno
                col = node.col_offset
                context = lines[line_num - 1] if 0 < line_num <= len(lines) else ""
                results.append({
                    "file": str(py_file.relative_to(project_root)),
                    "line": line_num,
                    "col": col,
                    "context": context.strip(),
                })
    # Sort by file then line
    results.sort(key=lambda r: (r["file"], r["line"]))
    return results


def _ast_find_callers(symbol: str, project_root: str) -> list[dict]:
    """Find all functions/methods in the project that call `symbol`.

    For each Python file, walks the AST looking for ast.Call nodes where
    the function name matches `symbol`. Returns the enclosing function/class name.
    """
    callers = []
    for py_file in _find_python_files(project_root):
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, OSError):
            continue

        # Walk all nodes, tracking the current enclosing function/class
        def _walk_calls(node, enclosing_name=None):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                enclosing_name = node.name
            elif isinstance(node, ast.ClassDef):
                enclosing_name = node.name

            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Call):
                    # Check if the call target matches the symbol
                    if isinstance(child.func, ast.Name) and child.func.id == symbol:
                        if enclosing_name and enclosing_name != symbol:
                            callers.append({
                                "name": enclosing_name,
                                "line": child.lineno,
                                "file": str(py_file.relative_to(project_root)),
                                "context": source.splitlines()[child.lineno - 1].strip()
                                if 0 < child.lineno <= len(source.splitlines()) else "",
                            })
                    elif isinstance(child.func, ast.Attribute) and child.func.attr == symbol:
                        # Method call like obj.symbol(...)
                        if enclosing_name and enclosing_name != symbol:
                            callers.append({
                                "name": enclosing_name,
                                "line": child.lineno,
                                "file": str(py_file.relative_to(project_root)),
                                "context": source.splitlines()[child.lineno - 1].strip()
                                if 0 < child.lineno <= len(source.splitlines()) else "",
                            })
                _walk_calls(child, enclosing_name)

        _walk_calls(tree)

    # Deduplicate (same caller name + line)
    seen = set()
    unique = []
    for c in callers:
        key = (c["name"], c["line"], c["file"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    unique.sort(key=lambda c: (c["file"], c["line"]))
    return unique


def _ast_find_callees(symbol: str, file_path: str, project_root: str) -> list[dict]:
    """Find all calls made within the function/class `symbol` in `file_path`.

    Parses the file, finds the target function/class, walks its body for ast.Call nodes.
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=file_path)
    except (SyntaxError, OSError) as e:
        return []

    callees = []

    # Find the target node
    target_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                target_node = node
                break

    if not target_node:
        return []

    # Walk the target node's body for calls
    for node in ast.walk(target_node):
        if isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name and name != symbol:
                callees.append({
                    "name": name,
                    "line": node.lineno,
                })

    # Deduplicate
    seen = set()
    unique = []
    for c in callees:
        key = (c["name"], c["line"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    unique.sort(key=lambda c: c["line"])
    return unique


def _tool_structural_analysis(args: dict[str, Any]) -> dict[str, Any]:
    analysis_type = args["analysis_type"]
    symbol = args.get("symbol")
    file_path = args.get("file")
    project_root = args.get("project_root", ".")

    if not file_path:
        return {"error": f"{analysis_type} analysis requires 'file'", "error_code": "INVALID_INPUT", "tool": "structural_analysis"}
    if not symbol and analysis_type in ("callers", "callees", "type_hierarchy", "references"):
        return {"error": f"{analysis_type} analysis requires 'symbol'", "error_code": "INVALID_INPUT", "tool": "structural_analysis"}

    # ── AST-based analyses (replacing broken jedi) ──

    if analysis_type == "references":
        refs = _ast_find_references(symbol, project_root)
        return {
            "analysis": "references",
            "symbol": symbol,
            "references": refs,
            "count": len(refs),
        }

    if analysis_type == "callers":
        callers = _ast_find_callers(symbol, project_root)
        return {
            "analysis": "callers",
            "symbol": symbol,
            "callers": callers,
            "count": len(callers),
        }

    if analysis_type == "callees":
        callees = _ast_find_callees(symbol, file_path, project_root)
        return {
            "analysis": "callees",
            "symbol": symbol,
            "callees": callees,
            "count": len(callees),
        }

    # ── jedi-based analyses (type_hierarchy, dependencies — leave as-is) ──

    import jedi

    if project_root:
        project = jedi.Project(path=project_root)
    elif file_path:
        project = jedi.Project(path=str(Path(file_path).parent))
    else:
        project = jedi.Project(path=".")

    if analysis_type == "type_hierarchy":
        if file_path:
            script = jedi.Script(path=file_path, project=project)
        else:
            script = jedi.Script("", project=project)
        try:
            defs = script.get_names(all_scopes=True)
            target = None
            for d in defs:
                if d.name == symbol and d.type == "class":
                    target = d
                    break
            if not target:
                return {"error": f"Class '{symbol}' not found", "error_code": "NOT_FOUND", "tool": "structural_analysis"}
            goto_results = target.goto()
            hierarchy = []
            for g in goto_results:
                hierarchy.append({
                    "name": g.name,
                    "type": g.type,
                    "line": g.line,
                    "file": str(g.module_path) if g.module_path else None,
                })
            return {"analysis": "type_hierarchy", "symbol": symbol, "hierarchy": hierarchy}
        except Exception as e:
            return {"error": str(e), "error_code": "INTERNAL", "tool": "structural_analysis"}

    elif analysis_type == "dependencies":
        script = jedi.Script(path=file_path, project=project)
        try:
            imports = script.get_names(all_scopes=True)
            deps = []
            for imp in imports:
                if imp.type == "module":
                    deps.append({
                        "name": imp.name,
                        "line": imp.line,
                    })
            return {"analysis": "dependencies", "file": file_path, "dependencies": deps, "count": len(deps)}
        except Exception as e:
            return {"error": str(e), "error_code": "INTERNAL", "tool": "structural_analysis"}

    return {"error": f"Unknown analysis type: {analysis_type}", "error_code": "INVALID_INPUT", "tool": "structural_analysis"}


# ─── find_references ──────────────────────────────────────────────────────

def _tool_find_references(args: dict[str, Any]) -> dict[str, Any]:
    """Find all references to a symbol across the codebase.

    Searches all Python files for ast.Name nodes matching the symbol.
    Returns file, line, column, and context for each occurrence.
    """
    symbol = args["symbol"]
    cwd = args.get("cwd", ".")
    file_filter = args.get("file")
    limit = int(args.get("limit", 100))

    if not symbol:
        return {"error": "symbol is required", "error_code": "INVALID_INPUT", "tool": "find_references"}

    try:
        refs = _ast_find_references(symbol, cwd)
    except Exception as e:
        return {"error": str(e), "error_code": "INTERNAL", "tool": "find_references"}

    # Filter to specific file if requested
    if file_filter:
        file_filter_path = str(Path(file_filter).resolve())
        filtered = []
        for ref in refs:
            ref_full = str(Path(cwd) / ref["file"])
            if ref_full == file_filter_path or ref["file"] == file_filter:
                filtered.append(ref)
        refs = filtered

    total = len(refs)
    truncated = total > limit
    if truncated:
        refs = refs[:limit]

    return {
        "symbol": symbol,
        "references": refs,
        "count": len(refs),
        "truncated": truncated,
        "total": total,
    }


# ─── impact_analysis ──────────────────────────────────────────────────────

# Helper functions moved to ast_tools.utils - wrappers defined earlier in this file


def _tool_impact_analysis(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze the impact of changing a file or symbol.

    Returns direct dependents, transitive dependents, test files affected,
    risk assessment, and (for symbol targets) callers.
    """
    target = args["target"]
    cwd = args.get("cwd", ".")

    from project_tools import find_project_root  # local import to avoid circular deps

    root = find_project_root(cwd)

    result: dict[str, Any] = {
        "target": target,
        "direct_dependents": [],
        "transitive_dependents": [],
        "test_files": [],
        "risk": "low",
        "fan_out": 0,
    }

    # Determine if target is a file path or a symbol name
    # If it ends with .py or resolves to an existing file, treat as file
    # Otherwise, treat as symbol name
    target_path = Path(target)
    is_file = False
    if target_path.exists() and str(target).endswith(".py"):
        is_file = True
        target_rel = _file_to_module(str(target_path.resolve()), root)
    elif (root / target).exists() and (root / target).is_file():
        is_file = True
        target_rel = str(Path(target))
    else:
        # Check if it exists relative to cwd
        cwd_path = Path(cwd) / target
        if cwd_path.exists() and str(target).endswith(".py"):
            is_file = True
            target_rel = _file_to_module(str(cwd_path.resolve()), root)

    if is_file:
        # ── File/module target: use dependency graph ──

        # Read dependency_graph.json if it exists
        dep_file = root / "references" / "dependency_graph.json"
        dep_graph: dict[str, list[str]] = {}
        if dep_file.exists():
            try:
                dep_graph = json.loads(dep_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                dep_graph = {}

        # If no dep_graph, build one from filesystem (basic scan)
        if not dep_graph:
            from project_tools import project_init
            try:
                project_init(str(root))
                if dep_file.exists():
                    dep_graph = json.loads(dep_file.read_text(encoding="utf-8"))
            except Exception:
                # Fallback: empty graph, only use AST-based caller detection
                dep_graph = {}

        reverse_deps = _build_reverse_deps(dep_graph)

        # Find direct dependents of the target module
        # Try several key formats: relative path, with/without .py, etc.
        lookup_keys = [
            target_rel,
            target_rel.replace("\\", "/"),
        ]
        # Also try without __init__.py for package dirs
        direct: list[str] = []
        for key in lookup_keys:
            direct.extend(reverse_deps.get(key, []))

        # Deduplicate
        direct = sorted(set(direct))
        result["direct_dependents"] = direct

        # Transitive dependents
        all_transitive: list[str] = []
        for d in direct:
            transitive = _get_transitive_deps(d, reverse_deps)
            all_transitive.extend(transitive)
        # Also from target itself
        all_transitive.extend(_get_transitive_deps(target_rel, reverse_deps))
        # Remove direct from transitive, and deduplicate
        transitive_only = sorted(set(all_transitive) - set(direct))
        result["transitive_dependents"] = transitive_only

        # Fan-out = direct dependents count
        fan_out = len(direct)
        result["fan_out"] = fan_out
        result["risk"] = _classify_risk(fan_out)

        # Identify test files among dependents
        all_affected = set(direct) | set(transitive_only)
        test_files = sorted(f for f in all_affected if _is_test_file(f))
        result["test_files"] = test_files

    else:
        # ── Symbol target: use AST-based caller search ──
        callers = _ast_find_callers(str(target), str(root))

        caller_files = sorted(set(c["file"] for c in callers))
        result["direct_dependents"] = caller_files
        result["callers"] = callers
        result["fan_out"] = len(caller_files)
        result["risk"] = _classify_risk(len(caller_files))

        # Test files among callers
        test_files = sorted(f for f in caller_files if _is_test_file(f))
        result["test_files"] = test_files

        # For symbols, transitive deps are not computed via dep graph
        result["transitive_dependents"] = []

    return result


# ─── module_imports ────────────────────────────────────────────────────────

def _tool_module_imports(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze module-level imports — fan-in and fan-out.

    Given a module path, finds:
    - fan_in: modules that import FROM the target
    - fan_out: modules that the target imports FROM
    - circular_deps: modules with mutual imports (A imports B, B imports A)
    - import_lines: specific import statements with file/line context
    """
    module = args["module"]
    cwd = args.get("cwd", ".")
    max_files = int(args.get("max_files", 500))

    from project_tools import find_project_root  # local import to avoid circular deps
    root = find_project_root(cwd)

    # Resolve module path to file path
    # Accept both dotted paths (nexusagent.core.worker) and file paths
    if module.endswith(".py") or "/" in module or "\\" in module:
        # It's a file path
        target_path = Path(module)
        if not target_path.is_absolute():
            target_path = Path(cwd) / module
        target_path = target_path.resolve()
    else:
        # It's a dotted module path like "nexusagent.core.worker"
        # Try to find the corresponding file
        parts = module.split(".")
        # Try as a package (nexusagent/core/worker/__init__.py)
        pkg_path = root / Path(*parts) / "__init__.py"
        if pkg_path.exists():
            target_path = pkg_path
        else:
            # Try as a module file (nexusagent/core/worker.py)
            mod_path = root / Path(*parts[:-1]) / (parts[-1] + ".py")
            if mod_path.exists():
                target_path = mod_path
            else:
                return {
                    "error": f"Module '{module}' not found in {root}",
                    "error_code": "NOT_FOUND",
                }

    target_str = str(target_path)
    target_rel = str(target_path.relative_to(root)) if target_path.is_relative_to(root) else target_str

    # Normalize: strip .py and __init__ for matching
    def _normalize_module_path(path_str: str) -> str:
        """Convert file path to dotted module path for matching."""
        p = path_str.replace("\\", "/")
        if p.endswith("/__init__.py"):
            p = p[: -len("/__init__.py")]
        elif p.endswith(".py"):
            p = p[:-3]
        return p.replace("/", ".")

    target_module = _normalize_module_path(target_rel)

    # Scan all Python files for imports
    fan_in: list[dict] = []  # modules that import FROM target
    fan_out: list[dict] = []  # modules that target imports from
    import_lines: list[dict] = []

    # First pass: find what the target module imports (fan_out)
    if target_path.exists():
        try:
            source = target_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=target_str)
        except (SyntaxError, OSError):
            tree = None

        if tree:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod_name = alias.name
                        fan_out.append({
                            "module": mod_name,
                            "line": node.lineno,
                            "type": "import",
                            "name": alias.asname or alias.name,
                        })
                        import_lines.append({
                            "file": target_rel,
                            "line": node.lineno,
                            "statement": f"import {mod_name}" + (f" as {alias.asname}" if alias.asname else ""),
                            "direction": "out",
                        })
                elif isinstance(node, ast.ImportFrom):
                    mod_name = node.module or ""
                    names = [a.name for a in node.names]
                    fan_out.append({
                        "module": mod_name,
                        "line": node.lineno,
                        "type": "from",
                        "names": names,
                    })
                    import_lines.append({
                        "file": target_rel,
                        "line": node.lineno,
                        "statement": f"from {mod_name} import {', '.join(names)}",
                        "direction": "out",
                    })

    # Second pass: find what imports FROM the target (fan_in)
    for py_file in _find_python_files(str(root), max_files=max_files):
        if str(py_file) == target_str:
            continue  # skip self

        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, OSError):
            continue

        file_rel = str(py_file.relative_to(root)) if py_file.is_relative_to(root) else str(py_file)
        file_module = _normalize_module_path(file_rel)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Check if the imported module matches target
                    imported = alias.name
                    if imported == target_module or imported.startswith(target_module + "."):
                        fan_in.append({
                            "file": file_rel,
                            "line": node.lineno,
                            "module": file_module,
                            "name": alias.asname or alias.name,
                            "type": "import",
                        })
                        import_lines.append({
                            "file": file_rel,
                            "line": node.lineno,
                            "statement": f"import {imported}" + (f" as {alias.asname}" if alias.asname else ""),
                            "direction": "in",
                        })
            elif isinstance(node, ast.ImportFrom):
                mod_name = node.module or ""
                # Check if the from-module matches target
                if mod_name == target_module or mod_name.startswith(target_module + "."):
                    names = [a.name for a in node.names]
                    fan_in.append({
                        "file": file_rel,
                        "line": node.lineno,
                        "module": file_module,
                        "names": names,
                        "type": "from",
                    })
                    import_lines.append({
                        "file": file_rel,
                        "line": node.lineno,
                        "statement": f"from {mod_name} import {', '.join(names)}",
                        "direction": "in",
                    })

    # Detect circular deps: modules that appear in both fan_in and fan_out
    fan_out_modules = {m["module"] for m in fan_out}
    fan_in_modules = {m["module"] for m in fan_in}
    circular_deps = sorted(fan_out_modules & fan_in_modules)

    return {
        "target": target_module,
        "target_file": target_rel,
        "fan_in_count": len(fan_in),
        "fan_out_count": len(fan_out),
        "fan_in": fan_in,
        "fan_out": fan_out,
        "circular_deps": circular_deps,
        "import_lines": import_lines,
    }


# ─── Main ─────────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "project":
        from project_tools import cli_main
        sys.exit(cli_main())
    else:
        import asyncio
        asyncio.run(main())
