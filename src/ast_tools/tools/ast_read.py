"""ast_read tool — extract API surface from Python files using AST."""

import ast
from typing import Any

from ast_tools.utils.annotations import (
    _annotation_to_str,
    _extract_all_names,
    _get_function_signature,
)
from ast_tools.utils.file_utils import validate_file_path


def _tool_ast_read(args: dict[str, Any]) -> dict[str, Any]:
    """Extract API surface from a Python file."""
    file_path = args["file"]
    project_path_arg = args.get("project_path")
    include_private = args.get("include_private", False)
    include_imports = args.get("include_imports", True)
    filter_by_type = args.get("filter_by_type")

    # Validate file path with security checks
    try:
        file_path = validate_file_path(
            file_path,
            project_path=project_path_arg,
            allow_nonexistent=False,
        )
    except ValueError as e:
        error_str = str(e)
        if "not found" in error_str.lower() or "exists" in error_str.lower():
            error_code = "NOT_FOUND"
        elif "traversal" in error_str.lower() or "outside" in error_str.lower():
            error_code = "PATH_TRAVERSAL"
        else:
            error_code = "INVALID_PATH"
        return {
            "error": str(e),
            "error_code": error_code,
            "tool": "ast_read",
        }

    try:
        source = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError as e:
        return {
            "error": f"File encoding error: {e}. Try saving as UTF-8.",
            "error_code": "ENCODING_ERROR",
            "tool": "ast_read",
        }

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        # Fallback: if AST parse fails, return line-based summary
        lines = source.splitlines()
        return {
            "file": str(file_path),
            "language": "python",
            "parse_error": f"AST parse failed: {e}",
            "fallback_summary": {
                "total_lines": len(lines),
                "non_empty_lines": sum(1 for line in lines if line.strip()),
                "has_unicode": any(ord(c) > 127 for line in lines for c in line),
                "first_50_lines": lines[:50],
            },
            "suggestion": "File may contain Unicode decoration or non-standard syntax. Try ast_grep for structural search, or read_file for raw content.",
            "tool": "ast_read",
        }

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
                    imports.append(
                        {
                            "module": alias.name,
                            "alias": alias.asname,
                            "line": node.lineno,
                        }
                    )
            elif isinstance(node, ast.ImportFrom) and _should_include("ImportFrom"):
                imports.append(
                    {
                        "module": node.module,
                        "names": [a.name for a in node.names],
                        "aliases": {a.name: a.asname for a in node.names if a.asname},
                        "line": node.lineno,
                    }
                )
        result["imports"] = imports

    # Check for __all__ export list
    all_names = _extract_all_names(tree)
    filtered_by_all = all_names is not None
    all_set = set(all_names) if filtered_by_all else set()

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
                    methods.append(
                        {
                            "name": item.name,
                            "signature": sig,
                            "line": item.lineno,
                            "end_line": item.end_lineno,
                            "docstring": ast.get_docstring(item),
                            "decorators": [ast.dump(d) for d in item.decorator_list],
                        }
                    )
            classes.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                    "bases": [_annotation_to_str(b) for b in node.bases],
                    "docstring": ast.get_docstring(node),
                    "methods": methods,
                    "decorators": [ast.dump(d) for d in node.decorator_list],
                }
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node_type = "FunctionDef" if isinstance(node, ast.FunctionDef) else "AsyncFunctionDef"
            if _should_include(node_type):
                if not include_private and node.name.startswith("_"):
                    continue
                if filtered_by_all and node.name not in all_set:
                    continue
                sig = _get_function_signature(node)
                functions.append(
                    {
                        "name": node.name,
                        "signature": sig,
                        "line": node.lineno,
                        "end_line": node.end_lineno,
                        "docstring": ast.get_docstring(node),
                        "decorators": [ast.dump(d) for d in node.decorator_list],
                    }
                )
        elif isinstance(node, ast.Assign) and _should_include("Assign"):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "__all__":
                        continue  # Skip __all__ assignment itself
                    if not include_private and target.id.startswith("_"):
                        continue
                    if filtered_by_all and target.id not in all_set:
                        continue
                    variables.append(
                        {
                            "name": target.id,
                            "line": node.lineno,
                            "value_preview": ast.dump(node.value)[:100],
                        }
                    )

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
