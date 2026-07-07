#!/usr/bin/env python3
"""File discovery and path utilities."""

import os
from pathlib import Path


def validate_file_path(
    file_path: str,
    project_path: str | None = None,
    allow_nonexistent: bool = False,
) -> Path:
    """Validate a file path against project boundaries for security.

    Args:
        file_path: Path to validate
        project_path: Optional project root to constrain to
        allow_nonexistent: If True, allow paths that don't exist yet

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path is outside project boundaries or attempts traversal
    """
    if not file_path:
        raise ValueError("File path cannot be empty")

    path = Path(file_path).resolve()

    # Check for traversal in original input
    if ".." in file_path:
        raise ValueError("Path traversal (..) not allowed")

    # If project_path provided, ensure file is within project
    if project_path:
        project_root = Path(project_path).resolve()
        try:
            if not path.is_relative_to(project_root):
                raise ValueError(f"Path {path} is outside project root {project_root}")
        except ValueError:
            # is_relative_to raises ValueError on Python < 3.9, or if not relative
            raise ValueError(f"Path {path} is outside project root {project_root}")

    # Check existence if required
    if not allow_nonexistent and not path.exists():
        raise ValueError(f"File not found: {path}")

    return path


def find_python_files(project_root: str, max_files: int | None = None) -> list[Path]:
    """Find all Python files under project_root, skipping common non-project dirs.

    Args:
        project_root: Root directory to search from
        max_files: Optional limit on number of files returned
    """
    skip_dirs = {
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
    root = Path(project_root)
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for filename in filenames:
            if filename.endswith(".py"):
                results.append(Path(dirpath) / filename)
                if max_files and len(results) >= max_files:
                    return results
    return results


def is_test_file(file_path: str) -> bool:
    """Check if a file is a test file based on naming conventions."""
    name = Path(file_path).name
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "/tests/" in file_path
        or "/testing/" in file_path
    )


def file_to_module(file_path: str, root: Path) -> str:
    """Convert a file path to a module name."""
    rel = Path(file_path).relative_to(root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # Remove .py
    return ".".join(parts)


def filter_top_level(matches: list, _pattern: str) -> list:
    """Filter matches to only top-level function/class definitions.

    Uses the column offset from ast-grep's range data: top-level definitions
    start at column 0, while methods inside classes are indented (column > 0).
    """
    top_level_matches = []
    for match in matches:
        if isinstance(match, dict):
            # JSON match: check column offset from range.start
            col = match.get("range", {}).get("start", {}).get("column", None)
            if col is not None:
                if col == 0:
                    top_level_matches.append(match)
            else:
                # No column info — include by default
                top_level_matches.append(match)
        elif isinstance(match, str):
            # Plain text mode: check if first non-whitespace char is at position 0
            if match and not match[0].isspace():
                top_level_matches.append(match)
    return top_level_matches
