"""structural_analysis tool — call graphs, type hierarchies, symbol references, dependencies."""

import ast
from pathlib import Path
from typing import Any

import jedi

from ast_tools.utils.file_utils import find_python_files


def _find_python_files(project_root: str, max_files: int | None = None) -> list[Path]:
    """Find all Python files in a project."""
    return find_python_files(project_root, max_files)


def _ast_find_references(symbol: str, project_root: str) -> list[dict]:
    """Find all references to `symbol` across the project using AST."""
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
    results.sort(key=lambda r: (r["file"], r["line"]))
    return results


def _ast_find_callers(symbol: str, project_root: str) -> list[dict]:
    """Find all functions/methods that call `symbol`."""
    callers = []
    for py_file in _find_python_files(project_root):
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, OSError):
            continue

        def _walk_calls(node, enclosing_name=None):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                enclosing_name = node.name
            elif isinstance(node, ast.ClassDef):
                enclosing_name = node.name
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == symbol:
                    callers.append({
                        "file": str(py_file.relative_to(project_root)),
                        "line": node.lineno,
                        "caller": enclosing_name or "<module>",
                        "context": source.splitlines()[node.lineno - 1].strip() if node.lineno <= len(source.splitlines()) else "",
                    })
                elif isinstance(node.func, ast.Attribute) and node.func.attr == symbol:
                    callers.append({
                        "file": str(py_file.relative_to(project_root)),
                        "line": node.lineno,
                        "caller": enclosing_name or "<module>",
                        "context": source.splitlines()[node.lineno - 1].strip() if node.lineno <= len(source.splitlines()) else "",
                    })
            for child in ast.iter_child_nodes(node):
                _walk_calls(child, enclosing_name)

        _walk_calls(tree)
    return callers


def _ast_find_callees(symbol: str, file_path: str, project_root: str) -> list[dict]:
    """Find all functions called BY `symbol`."""
    try:
        source = Path(file_path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=file_path)
    except (SyntaxError, OSError):
        return []

    callees = []
    in_target = False

    def _walk(node):
        nonlocal in_target
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol:
            in_target = True
            for child in ast.iter_child_nodes(node):
                _walk(child)
            in_target = False
        elif in_target and isinstance(node, ast.Call):
            callee_name = None
            if isinstance(node.func, ast.Name):
                callee_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                callee_name = node.func.attr
            if callee_name:
                callees.append({
                    "name": callee_name,
                    "line": node.lineno,
                    "context": source.splitlines()[node.lineno - 1].strip() if node.lineno <= len(source.splitlines()) else "",
                })

    _walk(tree)
    return callees


def _tool_structural_analysis(args: dict[str, Any]) -> dict[str, Any]:
    """Perform structural analysis on Python code."""
    analysis_type = args["analysis_type"]
    symbol = args.get("symbol")
    file_path = args.get("file")
    project_root = args.get("project_root", ".")

    if not file_path and analysis_type in ("callers", "callees", "references"):
        return {"error": f"{analysis_type} analysis requires 'file'", "error_code": "INVALID_INPUT", "tool": "structural_analysis"}
    if not symbol and analysis_type in ("callers", "callees", "references"):
        return {"error": f"{analysis_type} analysis requires 'symbol'", "error_code": "INVALID_INPUT", "tool": "structural_analysis"}

    if analysis_type == "references" and symbol:
        refs = _ast_find_references(symbol, project_root)
        return {
            "analysis": "references",
            "symbol": symbol,
            "references": refs,
            "count": len(refs),
        }

    if analysis_type == "callers" and symbol:
        callers = _ast_find_callers(symbol, project_root)
        return {
            "analysis": "callers",
            "symbol": symbol,
            "callers": callers,
            "count": len(callers),
        }

    if analysis_type == "callees" and symbol and file_path:
        callees = _ast_find_callees(symbol, file_path, project_root)
        return {
            "analysis": "callees",
            "symbol": symbol,
            "callees": callees,
            "count": len(callees),
        }

    # jedi-based analyses
    if project_root:
        project = jedi.Project(path=project_root)
    elif file_path:
        project = jedi.Project(path=str(Path(file_path).parent))
    else:
        project = jedi.Project(path=".")

    if analysis_type == "type_hierarchy":
        script = jedi.Script(path=file_path, project=project) if file_path else jedi.Script("", project=project)
        definitions = script.get_names(all_scopes=True)
        target = next((d for d in definitions if d.name == symbol and d.type == "class"), None)
        if not target:
            return {"error": f"Class '{symbol}' not found", "error_code": "NOT_FOUND", "tool": "structural_analysis"}
        try:
            hierarchy = []
            for g in target.goto():
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
            deps = [{"name": imp.name, "line": imp.line} for imp in imports if imp.type == "module"]
            return {"analysis": "dependencies", "file": file_path, "dependencies": deps, "count": len(deps)}
        except Exception as e:
            return {"error": str(e), "error_code": "INTERNAL", "tool": "structural_analysis"}

    return {"error": f"Unknown analysis type: {analysis_type}", "error_code": "INVALID_INPUT", "tool": "structural_analysis"}