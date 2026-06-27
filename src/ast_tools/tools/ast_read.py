"""ast_read tool — extract API surface from Python files using AST."""

import ast
from pathlib import Path
from typing import Any

from ast_tools.utils.annotations import (
    _annotation_to_str,
    _extract_all_names,
    _get_function_signature,
)


def _tool_ast_read(args: dict[str, Any]) -> dict[str, Any]:
    """Extract API surface from a Python file."""
    file_path = Path(args["file"]).resolve()
    include_private = args.get("include_private", False)
    include_imports = args.get("include_imports", True)
    filter_by_type = args.get("filter_by_type")

    if not file_path.exists():
        return {
            "error": f"File not found: {file_path}",
            "error_code": "NOT_FOUND",
            "tool": "ast_read",
        }

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
