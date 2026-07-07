#!/usr/bin/env python3
"""MCP tools for dependency graph analysis."""

import subprocess
from typing import Any

from .dependency import (
    find_circular_dependencies,
    find_dead_code,
    get_dependency_chain,
    get_external_dependencies,
)


def _tool_circular_dependencies(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper for circular_dependencies."""
    project_root = args.get("project_root", ".")
    return circular_dependencies(project_root)


def _tool_external_dependencies(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper for external_dependencies."""
    file_path = args.get("file_path")
    project_root = args.get("project_root", ".")
    if not file_path:
        return {"error": "file_path is required"}
    return external_dependencies(file_path, project_root)


def _tool_dead_code_detection(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper for dead_code_detection."""
    project_root = args.get("project_root", ".")
    entry_points = args.get("entry_points")
    return dead_code_detection(project_root, entry_points)


def _tool_dead_code_enhanced(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper for enhanced dead code detection.

    Enhanced version with:
    - Polymorphism tracking
    - Framework decorator detection
    - Entry point analysis
    - SCC cluster detection
    - __all__ exports check
    - Confidence scoring
    """
    project_root = args.get("project_root", ".")
    entry_points = args.get("entry_points")
    from .enhanced_dead_code import find_dead_code_enhanced

    return find_dead_code_enhanced(project_root, entry_points)


def _tool_dependency_chain(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper for dependency_chain."""
    symbol = args.get("symbol")
    file_path = args.get("file_path")
    project_root = args.get("project_root", ".")
    direction = args.get("direction", "both")
    depth = args.get("depth", 3)

    if not symbol or not file_path:
        return {"error": "symbol and file_path are required"}

    return dependency_chain(symbol, file_path, project_root, direction, depth)


def _tool_api_surface_diff(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper for api_surface_diff."""
    old_commit = args.get("old_commit")
    new_commit = args.get("new_commit")
    cwd = args.get("cwd", ".")

    if not old_commit or not new_commit:
        return {"error": "old_commit and new_commit are required"}

    return api_surface_diff(old_commit, new_commit, cwd)


def circular_dependencies(project_root: str) -> dict:
    """Detect circular imports in a Python project.

    Args:
        project_root: Root directory of the project

    Returns:
        List of cycles with severity ratings
    """
    cycles = find_circular_dependencies(project_root)
    return {"project_root": project_root, "cycles_found": len(cycles), "cycles": cycles}


def external_dependencies(file_path: str, project_root: str) -> dict:
    """Extract all third-party imports from a Python file.

    Args:
        file_path: Path to the Python file
        project_root: Root directory of the project

    Returns:
        Dict with file path and list of external dependencies
    """
    return get_external_dependencies(file_path, project_root)


def dead_code_detection(project_root: str, entry_points: list[str] | None = None) -> dict:
    """Find potentially unused code in a project.

    Args:
        project_root: Root directory of the project
        entry_points: List of known entry point files

    Returns:
        Dict with dead functions, classes, and variables
    """
    return find_dead_code(project_root, entry_points)


def dependency_chain(
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
    return get_dependency_chain(symbol, file_path, project_root, direction, depth)


def api_surface_diff(old_commit: str, new_commit: str, cwd: str = ".") -> dict:
    """Compare public API between two git commits.

    Args:
        old_commit: Old commit hash or ref
        new_commit: New commit hash or ref
        cwd: Working directory (default: current dir)

    Returns:
        Dict with added, removed, changed, and breaking changes
    """
    try:
        # Get changed files
        result = subprocess.run(
            ["git", "diff", "--name-only", old_commit, new_commit],
            capture_output=True,
            text=True,
            cwd=cwd,
        )

        if result.returncode != 0:
            return {
                "error": result.stderr,
                "added": [],
                "removed": [],
                "changed": [],
                "breaking_changes": [],
            }

        changed_files = [
            f.strip() for f in result.stdout.strip().split("\n") if f.strip() and f.endswith(".py")
        ]

        added = []
        removed = []
        changed = []
        breaking_changes = []

        for file_path in changed_files[:20]:  # Limit to 20 files
            try:
                # Get file content at old commit
                old_result = subprocess.run(
                    ["git", "show", f"{old_commit}:{file_path}"],
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                )

                # Get file content at new commit
                new_result = subprocess.run(
                    ["git", "show", f"{new_commit}:{file_path}"],
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                )

                if old_result.returncode == 0 and new_result.returncode == 0:
                    old_symbols = _extract_api(old_result.stdout)
                    new_symbols = _extract_api(new_result.stdout)

                    # Find additions
                    for sym in new_symbols:
                        if sym not in old_symbols:
                            added.append(sym)

                    # Find removals
                    for sym in old_symbols:
                        if sym not in new_symbols:
                            removed.append(sym)
                            breaking_changes.append(
                                {"symbol": sym, "file": file_path, "reason": "removed"}
                            )

            except Exception:
                continue

        return {
            "old_commit": old_commit,
            "new_commit": new_commit,
            "changed_files": changed_files,
            "added": added[:20],
            "removed": removed[:20],
            "changed": changed[:20],
            "breaking_changes": breaking_changes[:20],
            "summary": {
                "added_count": len(added),
                "removed_count": len(removed),
                "changed_count": len(changed),
                "breaking_count": len(breaking_changes),
            },
        }

    except Exception as e:
        return {"error": str(e), "added": [], "removed": [], "changed": [], "breaking_changes": []}


def _extract_api(source: str) -> set[str]:
    """Extract public API symbols from Python source."""
    import ast

    symbols = set()

    try:
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ) and not node.name.startswith("_"):
                symbols.add(node.name)
    except SyntaxError:
        pass

    return symbols
