#!/usr/bin/env python3
"""Dependency graph analysis tools for ast-tools.

Provides tools for analyzing code dependencies, detecting circular imports,
finding external dependencies, identifying dead code, and comparing API surfaces.
"""

from __future__ import annotations

import ast
import logging
import os
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Standard directories to skip when scanning projects
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".tox",
    ".eggs",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "site-packages",
}


def _iter_project_python_files(project_path: Path):
    """Yield Python files in a project, skipping virtual envs and other non-project dirs."""
    for dirpath, dirnames, filenames in os.walk(project_path):
        # Modify dirnames in-place to skip excluded directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in filenames:
            if filename.endswith(".py"):
                yield Path(dirpath) / filename


def build_import_graph(project_root: str) -> dict[str, set[str]]:
    """Build a graph of module imports.

    Args:
        project_root: Root directory of the project

    Returns:
        Dict mapping module paths to set of imported module paths
    """
    graph = defaultdict(set)
    project_path = Path(project_root)

    for py_file in _iter_project_python_files(project_path):
        rel_path = py_file.relative_to(project_path)
        module = str(rel_path.with_suffix("")).replace("/", ".")

        try:
            with open(py_file) as f:
                source = f.read()

            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        graph[module].add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    graph[module].add(node.module.split(".")[0])
        except (SyntaxError, UnicodeDecodeError):
            logger.debug(f"Skipping unparseable file: {py_file}")

    return graph


def find_circular_dependencies(project_root: str) -> list[dict]:
    """Detect circular imports in a Python project.

    Args:
        project_root: Root directory of the project

    Returns:
        List of cycles, each with cycle path and severity
    """
    graph = build_import_graph(project_root)
    cycles = []
    visited = set()
    rec_stack = set()

    def dfs(node: str, path: list[str]) -> list[str] | None:
        """DFS to detect cycles."""
        if node in rec_stack:
            # Found a cycle
            cycle_start = path.index(node)
            return [*path[cycle_start:], node]

        if node in visited:
            return None

        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            cycle = dfs(neighbor, path)
            if cycle:
                return cycle

        path.pop()
        rec_stack.remove(node)
        return None

    for module in graph:
        if module not in visited:
            cycle = dfs(module, [])
            if cycle and cycle not in [c["cycle"] for c in cycles]:
                severity = "high" if len(cycle) <= 3 else "medium"
                cycles.append({"cycle": cycle, "severity": severity, "length": len(cycle) - 1})

    return sorted(cycles, key=lambda c: c["severity"], reverse=True)


def get_external_dependencies(file_path: str, project_root: str) -> dict:
    """Extract all third-party imports from a Python file.

    Args:
        file_path: Path to the Python file
        project_root: Root directory of the project

    Returns:
        Dict with file path and list of external dependencies
    """
    stdlib_modules = {
        "ast",
        "asyncio",
        "collections",
        "contextlib",
        "copy",
        "datetime",
        "enum",
        "functools",
        "hashlib",
        "http",
        "importlib",
        "inspect",
        "itertools",
        "json",
        "logging",
        "math",
        "os",
        "pathlib",
        "re",
        "shutil",
        "signal",
        "socket",
        "sqlite3",
        "string",
        "struct",
        "subprocess",
        "sys",
        "tempfile",
        "threading",
        "time",
        "traceback",
        "typing",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "weakref",
        "xml",
        "zipfile",
        "zlib",
    }

    # Get local modules
    local_modules = set()
    project_path = Path(project_root)
    for py_file in _iter_project_python_files(project_path):
        rel_path = py_file.relative_to(project_path)
        module_parts = str(rel_path.with_suffix("")).split("/")
        if module_parts:
            local_modules.add(module_parts[0])

    externals = []

    try:
        with open(file_path) as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".")[0]
                    if module not in stdlib_modules and module not in local_modules:
                        externals.append(
                            {
                                "module": alias.name,
                                "line": node.lineno,
                                "symbols": [alias.asname or alias.name],
                            }
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module.split(".")[0]
                if module not in stdlib_modules and module not in local_modules:
                    symbols = [alias.asname or alias.name for alias in node.names]
                    # Check if we already have this module
                    found = False
                    for ext in externals:
                        if ext["module"] == node.module:
                            ext["symbols"].extend(symbols)
                            found = True
                            break
                    if not found:
                        externals.append(
                            {"module": node.module, "line": node.lineno, "symbols": symbols}
                        )
    except (SyntaxError, UnicodeDecodeError) as e:
        logger.error(f"Failed to parse {file_path}: {e}")

    return {"file": file_path, "externals": externals, "external_count": len(externals)}


def find_dead_code(project_root: str, entry_points: list[str] | None = None) -> dict:
    """Find potentially unused code in a project.

    Args:
        project_root: Root directory of the project
        entry_points: List of known entry point files (e.g., main.py, __init__.py)

    Returns:
        Dict with dead functions, classes, and variables
    """
    project_path = Path(project_root)

    # Collect all definitions
    definitions = defaultdict(list)  # symbol -> [(file, line, type)]
    references = defaultdict(list)  # symbol -> [(file, line)]

    for py_file in _iter_project_python_files(project_path):
        if py_file.name.startswith("test_"):
            continue

        rel_path = str(py_file.relative_to(project_path))

        try:
            with open(py_file) as f:
                source = f.read()

            tree = ast.parse(source)

            # Collect definitions
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and not node.name.startswith("_"):  # Skip private
                    definitions[node.name].append(
                        {"file": rel_path, "line": node.lineno, "type": "function"}
                    )
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    definitions[node.name].append(
                        {"file": rel_path, "line": node.lineno, "type": "class"}
                    )

                # Collect references (Names that are loaded, not stored)
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    references[node.id].append(rel_path)

        except (SyntaxError, UnicodeDecodeError):
            logger.debug(f"Skipping unparseable file: {py_file}")

    # Find dead code (defined but never referenced)
    dead_functions = []
    dead_classes = []

    for symbol, defs in definitions.items():
        if symbol not in references or len(references[symbol]) == 0:
            for defn in defs:
                if defn["type"] == "function":
                    dead_functions.append(
                        {
                            "name": symbol,
                            "file": f"{defn['file']}:{defn['line']}",
                            "confidence": 0.8,  # High confidence but not certain
                        }
                    )
                elif defn["type"] == "class":
                    dead_classes.append(
                        {
                            "name": symbol,
                            "file": f"{defn['file']}:{defn['line']}",
                            "confidence": 0.8,
                        }
                    )

    return {
        "dead_functions": dead_functions[:50],  # Limit results
        "dead_classes": dead_classes[:50],
        "dead_variables": [],  # Could be added in future
        "summary": {
            "total_dead_functions": len(dead_functions),
            "total_dead_classes": len(dead_classes),
        },
    }


def get_dependency_chain(
    symbol: str, file_path: str, project_root: str, direction: str = "both", depth: int = 3
) -> dict:
    """Get full dependency chain for a symbol.

    Args:
        symbol: Name of the symbol to analyze
        file_path: File containing the symbol
        project_root: Root directory of the project
        direction: "upstream" (depends_on), "downstream" (used_by), or "both"
        depth: Maximum depth to traverse

    Returns:
        Dependency tree with depends_on and used_by branches
    """
    # This is a simplified version - full implementation would use
    # the semantic DB and LSP for accurate cross-file tracing
    project_path = Path(project_root)

    result = {"symbol": symbol, "file": file_path, "depends_on": [], "used_by": []}

    if direction in ("upstream", "both"):
        # Find what this symbol imports/uses
        try:
            abs_path = project_path / file_path
            with open(abs_path) as f:
                source = f.read()

            tree = ast.parse(source)

            # Find the symbol definition
            for node in ast.walk(tree):
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    and node.name == symbol
                ):
                    # Collect imports and references within the function
                    for child in ast.walk(node):
                        if (
                            isinstance(child, ast.Name)
                            and isinstance(child.ctx, ast.Load)
                            and child.id != symbol
                        ):
                            result["depends_on"].append(
                                {"symbol": child.id, "file": file_path, "depth": 1}
                            )
                    break
        except (FileNotFoundError, SyntaxError):
            pass

    if direction in ("downstream", "both"):
        # Find what uses this symbol (simplified - searches all files)
        for py_file in project_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file) as f:
                    source = f.read()

                if symbol in source:
                    rel_path = str(py_file.relative_to(project_path))
                    if rel_path != file_path:  # Exclude self
                        result["used_by"].append({"symbol": symbol, "file": rel_path, "depth": 1})
            except (SyntaxError, UnicodeDecodeError):
                continue

    # Deduplicate
    result["depends_on"] = list({item["symbol"]: item for item in result["depends_on"]}.values())
    result["used_by"] = list({item["file"]: item for item in result["used_by"]}.values())

    return result
