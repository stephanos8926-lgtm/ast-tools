"""codebase_summary tool — high-level architecture overview."""

import ast
import json
import os
from pathlib import Path
from typing import Any

from ast_tools.utils.file_utils import find_python_files


def _tool_codebase_summary(args: dict[str, Any]) -> dict[str, Any]:
    """High-level architecture overview of a codebase.
    
    Returns a compact summary with: project name, languages, module count,
    symbol count, entry points, test framework, directory tree,
    top imported modules, and test-to-source mapping.
    Optimized LLM context — under 500 tokens.
    """
    cwd = args.get("cwd", ".")
    
    try:
        from project_tools import project_info_summary, find_project_root
        summary = project_info_summary(cwd)
    except Exception as e:
        return {"error": str(e), "error_code": "INTERNAL", "tool": "codebase_summary"}
    
    root = find_project_root(cwd)
    # Build directory tree (2 levels deep)
    skip_dirs = {
        ".git", "__pycache__", ".venv", "venv", "node_modules",
        ".tox", ".eggs", "build", "dist", ".mypy_cache", ".pytest_cache",
        ".idea", ".vscode", "site-packages", "references",
    }
    tree = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).relative_to(root).parts)
            if depth > 2:
                dirnames.clear()
                continue
            dirnames[:] = sorted(d for d in dirnames if d not in skip_dirs and not d.startswith("."))
            rel = str(Path(dirpath).relative_to(root))
            if depth <= 2:
                for fn in sorted(filenames):
                    if not fn.startswith(".") and not fn.endswith((".pyc", ".pyo")):
                        if rel != ".":
                            tree.append(f"{rel}/{fn}")
                        else:
                            tree.append(fn)
    except OSError:
        pass
    
    # Top imported modules from dependency_graph.json
    top_imports: list[str] = []
    dep_file = root / "references" / "dependency_graph.json"
    if dep_file.exists():
        try:
            dep_graph = json.loads(dep_file.read_text(encoding="utf-8"))
            import_counts: dict[str, int] = {}
            for _src, targets in dep_graph.items():
                for t in targets:
                    top_imports_key = t.rsplit("/", 1)[-1] if "/" in t else t
                    top_imports_key = top_imports_key.replace(".py", "")
                    import_counts[top_imports_key] = import_counts.get(top_imports_key, 0) + 1
            sorted_imports = sorted(import_counts.items(), key=lambda x: -x[1])
            top_imports = [name for name, _count in sorted_imports[:10]]
        except (json.JSONDecodeError, OSError):
            pass
    
    # Test-to-source mapping
    test_mapping: dict[str, list[str]] = {}
    try:
        for py_file in find_python_files(str(root)):
            rel = str(py_file.relative_to(root))
            if "test" in py_file.name.lower() or "tests" in py_file.parts:
                try:
                    source = py_file.read_text(encoding="utf-8", errors="replace")
                    tree_ast = ast.parse(source, filename=str(py_file))
                    for node in ast.walk(tree_ast):
                        if isinstance(node, ast.ImportFrom) and node.module:
                            test_mapping.setdefault(rel, []).append(node.module)
                        elif isinstance(node, ast.Import):
                            for alias in node.names:
                                test_mapping.setdefault(rel, []).append(alias.name)
                except (SyntaxError, OSError):
                    pass
        # Deduplicate
        for k in test_mapping:
            test_mapping[k] = sorted(set(test_mapping[k]))
    except Exception:
        pass
    
    result = dict(summary)
    # Compact tree: group by directory, count files per dir
    tree_dirs: dict[str, int] = {}
    for entry in tree[:50]:
        parts = entry.split("/")
        if len(parts) > 1:
            tree_dirs[parts[0]] = tree_dirs.get(parts[0], 0) + 1
        else:
            tree_dirs["."] = tree_dirs.get(".", 0) + 1
    compact_tree = {f"{k}": v for k, v in sorted(tree_dirs.items())}
    result["tree"] = compact_tree
    if top_imports:
        result["top_imports"] = top_imports[:5]
    # Skip test_mapping by default — too large. Keep only first 5 entries.
    if test_mapping:
        trimmed_tests = {k: v[:3] for k, v in list(test_mapping.items())[:5]}
        result["test_mapping"] = trimmed_tests
    return result