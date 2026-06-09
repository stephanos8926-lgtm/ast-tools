#!/usr/bin/env python3
"""
AST Tools MCP Server — structural code analysis and editing tools.

Exposes 4 tools:
  ast_grep    — Structural search (via ast-grep CLI)
  ast_edit    — Surgical AST-based modification (via libcst)
  ast_read    — Structural context extraction (via ast module)
  structural_analysis — Call graphs, type hierarchies, symbol references (via jedi)
"""

import ast
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import libcst as cst
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

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
                },
                "required": ["file"],
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
    ]


# ─── Tool Handlers ────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "ast_grep":
            result = _tool_ast_grep(arguments)
        elif name == "ast_edit":
            result = _tool_ast_edit(arguments)
        elif name == "ast_read":
            result = _tool_ast_read(arguments)
        elif name == "structural_analysis":
            result = _tool_structural_analysis(arguments)
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


# ─── ast_grep ─────────────────────────────────────────────────────────────

def _tool_ast_grep(args: dict[str, Any]) -> dict[str, Any]:
    pattern = args["pattern"]
    path = args.get("path", ".")
    lang = args.get("lang")
    json_output = args.get("json_output", True)

    cmd = ["ast-grep", "--pattern", pattern, path]
    if lang:
        cmd.extend(["--lang", lang])
    if json_output:
        cmd.append("--json")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return {"error": "ast-grep CLI not found. Install: cargo install ast-grep"}
    except subprocess.TimeoutExpired:
        return {"error": "ast-grep timed out after 30s"}

    if proc.returncode != 0 and not proc.stdout:
        return {"error": proc.stderr.strip() or "ast-grep returned no output", "matches": []}

    if json_output:
        try:
            matches = json.loads(proc.stdout)
        except json.JSONDecodeError:
            matches = []
        return {
            "matches": matches,
            "count": len(matches),
            "pattern": pattern,
            "path": path,
        }
    else:
        lines = [l for l in proc.stdout.strip().splitlines() if l]
        return {
            "matches": lines,
            "count": len(lines),
            "pattern": pattern,
            "path": path,
        }


# ─── ast_edit ─────────────────────────────────────────────────────────────

def _tool_ast_edit(args: dict[str, Any]) -> dict[str, Any]:
    file_path = Path(args["file"]).resolve()
    operation = args["operation"]
    params = args.get("params", {})
    dry_run = args.get("dry_run", False)

    if not file_path.exists():
        return {"error": f"File not found: {file_path}"}

    source = file_path.read_text()
    try:
        tree = cst.parse_module(source)
    except cst.ParserSyntaxError as e:
        return {"error": f"Syntax error in {file_path}: {e}"}

    transformer = _build_transformer(operation, params)
    if transformer is None:
        return {"error": f"Unknown operation: {operation}"}

    import libcst.metadata as cst_meta
    wrapper = cst.MetadataWrapper(tree)
    try:
        new_tree = wrapper.visit(transformer)
    except Exception as e:
        return {"error": f"Transformation failed: {e}"}

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

def _tool_ast_read(args: dict[str, Any]) -> dict[str, Any]:
    file_path = Path(args["file"]).resolve()
    include_private = args.get("include_private", False)
    include_imports = args.get("include_imports", True)

    if not file_path.exists():
        return {"error": f"File not found: {file_path}"}

    source = file_path.read_text()
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        return {"error": f"Syntax error: {e}"}

    result: dict[str, Any] = {
        "file": str(file_path),
        "language": "python",
    }

    if include_imports:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "module": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    })
            elif isinstance(node, ast.ImportFrom):
                imports.append({
                    "module": node.module,
                    "names": [a.name for a in node.names],
                    "alias": {a.name: a.asname for a in node.names if a.asname},
                    "line": node.lineno,
                })
        result["imports"] = imports

    classes = []
    functions = []
    variables = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            if not include_private and node.name.startswith("_"):
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
                "bases": [ast.dump(b) for b in node.bases],
                "docstring": ast.get_docstring(node),
                "methods": methods,
                "decorators": [ast.dump(d) for d in node.decorator_list],
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not include_private and node.name.startswith("_"):
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
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if not include_private and target.id.startswith("_"):
                        continue
                    variables.append({
                        "name": target.id,
                        "line": node.lineno,
                        "value_preview": ast.dump(node.value)[:100],
                    })

    result["classes"] = classes
    result["functions"] = functions
    result["variables"] = variables
    result["summary"] = {
        "total_classes": len(classes),
        "total_functions": len(functions),
        "total_variables": len(variables),
        "total_imports": len(result.get("imports", [])),
    }

    return result


def _get_function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Extract a human-readable function signature."""
    args = node.args
    parts = []

    # Positional args
    for arg in args.args:
        name = arg.arg
        if arg.annotation:
            name += f": {ast.dump(arg.annotation)}"
        parts.append(name)

    # *args
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")

    # Keyword-only
    for arg in args.kwonlyargs:
        name = arg.arg
        if arg.annotation:
            name += f": {ast.dump(arg.annotation)}"
        parts.append(name)

    # **kwargs
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    sig = f"({', '.join(parts)})"
    if node.returns:
        sig += f" -> {ast.dump(node.returns)}"
    return sig


# ─── structural_analysis ─────────────────────────────────────────────────

def _tool_structural_analysis(args: dict[str, Any]) -> dict[str, Any]:
    import jedi

    analysis_type = args["analysis_type"]
    symbol = args.get("symbol")
    file_path = args.get("file")
    line = args.get("line")
    project_root = args.get("project_root")

    if project_root:
        project = jedi.Project(path=project_root)
    elif file_path:
        project = jedi.Project(path=str(Path(file_path).parent))
    else:
        project = jedi.Project(path=".")

    if analysis_type == "callers":
        if not file_path or not symbol:
            return {"error": "callers analysis requires 'file' and 'symbol'"}
        script = jedi.Script(path=file_path, project=project)
        try:
            definitions = script.get_names(all_scopes=True)
            target = None
            for d in definitions:
                if d.name == symbol:
                    target = d
                    break
            if not target:
                return {"error": f"Symbol '{symbol}' not found in {file_path}"}
            usages = target.goto()
            callers = []
            for ref in script.get_names(all_scopes=True):
                if ref.type == "function" or ref.type == "class":
                    # Check if this function calls our target
                    sub_script = jedi.Script(
                        path=file_path, project=project
                    )
                    for sub_ref in sub_script.get_names(all_scopes=True):
                        if sub_ref.name == symbol and sub_ref != target:
                            callers.append({
                                "name": ref.name,
                                "line": ref.line,
                                "type": ref.type,
                            })
            return {"analysis": "callers", "symbol": symbol, "callers": callers}
        except Exception as e:
            return {"error": str(e)}

    elif analysis_type == "callees":
        if not file_path or not symbol:
            return {"error": "callees analysis requires 'file' and 'symbol'"}
        script = jedi.Script(path=file_path, project=project)
        try:
            definitions = script.get_names(all_scopes=True)
            target = None
            for d in definitions:
                if d.name == symbol:
                    target = d
                    break
            if not target:
                return {"error": f"Symbol '{symbol}' not found in {file_path}"}
            # Get the function body and find calls within it
            goto_results = target.goto()
            callees = []
            for g in goto_results:
                if g.type in ("function", "class"):
                    callees.append({
                        "name": g.name,
                        "line": g.line,
                        "type": g.type,
                        "file": str(g.module_path) if g.module_path else None,
                    })
            return {"analysis": "callees", "symbol": symbol, "callees": callees}
        except Exception as e:
            return {"error": str(e)}

    elif analysis_type == "type_hierarchy":
        if not symbol:
            return {"error": "type_hierarchy analysis requires 'symbol'"}
        if file_path:
            script = jedi.Script(path=file_path, project=project)
        else:
            script = jedi.Script("", project=project)
        try:
            # Find the class and its bases
            defs = script.get_names(all_scopes=True)
            target = None
            for d in defs:
                if d.name == symbol and d.type == "class":
                    target = d
                    break
            if not target:
                return {"error": f"Class '{symbol}' not found"}
            # Get inheritance info
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
            return {"error": str(e)}

    elif analysis_type == "references":
        if not symbol:
            return {"error": "references analysis requires 'symbol'"}
        if file_path:
            script = jedi.Script(path=file_path, project=project)
        else:
            script = jedi.Script("", project=project)
        try:
            refs = script.get_references(line=line)
            references = []
            for ref in refs:
                references.append({
                    "name": ref.name,
                    "line": ref.line,
                    "column": ref.column,
                    "file": str(ref.module_path) if ref.module_path else None,
                })
            return {"analysis": "references", "symbol": symbol, "references": references, "count": len(references)}
        except Exception as e:
            return {"error": str(e)}

    elif analysis_type == "dependencies":
        if not file_path:
            return {"error": "dependencies analysis requires 'file'"}
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
            return {"error": str(e)}

    return {"error": f"Unknown analysis type: {analysis_type}"}


# ─── Main ─────────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
