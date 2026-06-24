"""module_imports tool — analyze module-level imports (fan-in/fan-out)."""

import ast
from pathlib import Path
from typing import Any

from ast_tools.utils.file_utils import find_python_files


def _normalize_module_path(path_str: str) -> str:
    """Convert file path to dotted module path for matching."""
    p = path_str.replace("\\", "/")
    if p.endswith("/__init__.py"):
        p = p[: -len("/__init__.py")]
    elif p.endswith(".py"):
        p = p[:-3]
    return p.replace("/", ".")


def _tool_module_imports(args: dict[str, Any]) -> dict[str, Any]:
    """Analyze module-level imports — fan-in and fan-out."""
    module = args["module"]
    cwd = args.get("cwd", ".")
    max_files = int(args.get("max_files", 500))

    from project_tools import find_project_root
    root = find_project_root(cwd)

    # Resolve module path to file path
    if module.endswith(".py") or "/" in module or "\\" in module:
        target_path = Path(module)
        if not target_path.is_absolute():
            target_path = Path(cwd) / module
        target_path = target_path.resolve()
    else:
        parts = module.split(".")
        pkg_path = root / Path(*parts) / "__init__.py"
        if pkg_path.exists():
            target_path = pkg_path
        else:
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
    target_module = _normalize_module_path(target_rel)

    fan_in: list[dict] = []
    fan_out: list[dict] = []
    import_lines: list[dict] = []
    circular_deps: list[str] = []

    # Fan-out: what target imports
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

    # Fan-in: what imports from target
    for py_file in find_python_files(str(root), max_files=max_files):
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, OSError):
            continue

        rel = str(py_file.relative_to(root)) if py_file.is_relative_to(root) else str(py_file)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == target_module or alias.name.startswith(target_module + "."):
                        fan_in.append({
                            "module": alias.name,
                            "file": rel,
                            "line": node.lineno,
                            "type": "import",
                        })
                        import_lines.append({
                            "file": rel,
                            "line": node.lineno,
                            "statement": f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else ""),
                            "direction": "in",
                        })
            elif isinstance(node, ast.ImportFrom):
                if node.module and (node.module == target_module or node.module.startswith(target_module + ".")):
                    names = [a.name for a in node.names]
                    fan_in.append({
                        "module": node.module,
                        "file": rel,
                        "line": node.lineno,
                        "type": "from",
                        "names": names,
                    })
                    import_lines.append({
                        "file": rel,
                        "line": node.lineno,
                        "statement": f"from {node.module} import {', '.join(names)}",
                        "direction": "in",
                    })

    # Detect circular deps
    all_modules = set()
    for f in find_python_files(str(root), max_files=max_files):
        try:
            src = f.read_text(encoding="utf-8", errors="replace")
            tr = ast.parse(src)
            for n in ast.walk(tr):
                if isinstance(n, ast.Import):
                    for a in n.names:
                        all_modules.add(a.name.split(".")[0])
                elif isinstance(n, ast.ImportFrom) and n.module:
                    all_modules.add(n.module.split(".")[0])
        except (SyntaxError, OSError):
            continue

    if target_module in all_modules:
        circular_deps = [target_module]

    return {
        "module": target_module,
        "file": target_rel,
        "fan_in": fan_in,
        "fan_out": fan_out,
        "circular_deps": circular_deps,
        "import_lines": import_lines,
        "summary": {
            "fan_in_count": len(fan_in),
            "fan_out_count": len(fan_out),
            "circular_count": len(circular_deps),
        },
    }
