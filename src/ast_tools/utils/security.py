"""Security utilities for path validation and input sanitization."""

import os
import re
from pathlib import Path
from typing import List, Optional


def validate_project_path(
    path_str: str,
    allowed_roots: list[Path] | None = None,
    allow_cwd: bool = True,
) -> Path:
    """Validate and resolve a project path with security checks.

    Args:
        path_str: User-provided path string
        allowed_roots: Additional allowed root directories
        allow_cwd: Whether to allow current working directory

    Returns:
        Resolved Path object within allowed boundaries

    Raises:
        ValueError: If path is outside allowed roots or contains traversal patterns
    """
    if not path_str or not path_str.strip():
        raise ValueError("Path cannot be empty")

    # Resolve the path
    try:
        path = Path(path_str).resolve(strict=False)
    except (OSError, ValueError) as e:
        raise ValueError(f"Invalid path: {e}")

    # Check for path traversal patterns before resolution
    if '..' in path_str:
        raise ValueError("Path traversal (..) is not allowed")

    # Build allowed roots
    roots = []
    if allowed_roots:
        roots.extend([r.resolve() for r in allowed_roots])

    if allow_cwd:
        try:
            roots.append(Path.cwd().resolve())
        except (OSError, ValueError):
            pass

    # Add temp directories as allowed (for testing)
    import tempfile
    temp_root = Path(tempfile.gettempdir()).resolve()
    roots.append(temp_root)

    # Add common workspace directories
    workspace_roots = [
        Path.home() / "Workspaces",
        Path.home() / "projects",
        Path.home() / "code",
        Path("/workspace"),
        Path("/opt/workspace"),
    ]
    for root in workspace_roots:
        if root.exists():
            roots.append(root.resolve())

    # Deduplicate
    roots = list(dict.fromkeys(roots))

    # Check if path is within any allowed root
    real_path = path.resolve(strict=False)

    path_allowed = False
    for root in roots:
        try:
            if path.is_relative_to(root) or real_path.is_relative_to(root):
                path_allowed = True
                break
        except (ValueError, OSError):
            continue

    if not path_allowed:
        allowed_str = ", ".join(str(r) for r in roots[:5])
        raise ValueError(
            f"Path '{path}' is outside allowed directories. "
            f"Allowed roots: {allowed_str}"
        )

    # Ensure it's a directory (or will be created as one)
    if path.exists() and not path.is_dir():
        raise ValueError(f"Path exists but is not a directory: {path}")

    return path


def sanitize_search_query(query: str, max_length: int = 500) -> str:
    """Sanitize search query to prevent injection.

    Args:
        query: User search query
        max_length: Maximum allowed length

    Returns:
        Sanitized query string
    """
    if not query:
        return ""

    # Limit length
    query = query[:max_length]

    # Remove boolean operators first
    query = re.sub(r'\b(OR|AND|NOT|NEAR)\b', ' ', query, flags=re.IGNORECASE)

    # Escape quotes (BEFORE special char escaping)
    query = query.replace('"', '""')

    # Escape special chars (but preserve quotes and slashes)
    query = re.sub(r'[()*:<>^@]', ' ', query)

    # Clean up whitespace
    query = re.sub(r'\s+', ' ', query).strip()

    return query


def validate_limit(limit: int, max_limit: int = 1000, default: int = 50) -> int:
    """Validate and clamp limit parameter.

    Args:
        limit: Requested limit
        max_limit: Maximum allowed limit
        default: Default if None or invalid

    Returns:
        Validated limit value
    """
    if limit is None:
        return default

    try:
        limit = int(limit)
    except (ValueError, TypeError):
        return default

    return max(1, min(limit, max_limit))


def validate_timeout(timeout: int, max_timeout: int = 300, default: int = 30) -> int:
    """Validate and clamp timeout parameter.

    Args:
        timeout: Requested timeout in seconds
        max_timeout: Maximum allowed timeout
        default: Default if None or invalid

    Returns:
        Validated timeout value
    """
    if timeout is None:
        return default

    try:
        timeout = int(timeout)
    except (ValueError, TypeError):
        return default

    return max(1, min(timeout, max_timeout))


# Backwards compatibility - these functions are also in queries.py
def sanitize_fts5_query(query: str) -> str:
    """Sanitize FTS5 query to prevent operator injection.

    This is a duplicate of the function in queries.py for CLI use.
    """
    return sanitize_search_query(query, max_length=500)