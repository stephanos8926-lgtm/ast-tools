"""Watchdog path validation guards.

Prevents the 2026-08-11 inotify-exhaustion incident: recursively watching
an over-broad path (e.g. the entire home directory `/home/sysop`) blew the
inotify watch limit, producing "No space left on device" and taking down the
daemon.

The guards reject, with a clear human-readable error, any watch path that
would silently cause this class of failure:
  - non-existent paths
  - files (not directories)
  - the filesystem root `/`
  - the user's home directory or any directory that contains it
  - obvious build/cache/virtualenv directories (wasteful, high fan-out)

Usage:
    ok, errors = validate_watch_paths(["/my/project", "/home/sysop"])
    if not ok:
        log.warning("Refusing to watch:\n%s", "\n".join(errors))
"""

from __future__ import annotations

from pathlib import Path

# Directories that are never worth recursively watching — they explode the
# inotify count (venv, node_modules) or are churn (build artifacts).
_UNWATCHABLE_PARTS = {
    "__pycache__",
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    ".egg-info",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".cache",
}

# Paths that are explicitly forbidden because they would recursively watch
# the user's home tree (the 2026-08-11 incident). These are exact or
# parent-of-home matches after resolution.
def _home_and_parents() -> set[Path]:
    """Return the user's home directory and all its parent directories."""
    home = Path.home().resolve()
    return {home, *home.parents}


def _classify_reason(path: Path) -> str | None:
    """Return a human-readable rejection reason, or None if path is safe."""
    resolved = path.resolve()

    # Existence
    if not resolved.exists():
        return f"Path does not exist: {path}"

    # Directory check
    if not resolved.is_dir():
        return f"Path is not a directory: {path}"

    # Filesystem root
    if resolved.parent == resolved:
        return f"Refusing to recursively watch filesystem root: {path}"

    # User's home directory or any directory that contains it
    # (e.g. /home, /home/sysop) — the exact 2026-08-11 failure mode.
    # We reject if:
    #   - resolved EQUALS a forbidden path (home or its parents)
    #   - resolved CONTAINS a forbidden path (resolved is an ancestor of forbidden)
    for forbidden in _home_and_parents():
        if resolved == forbidden or forbidden.is_relative_to(resolved):
            return (
                f"Refusing to watch a path that would recurse into the user's "
                f"home directory ({Path.home()}): {path}"
            )

    # Unwatchable subdirectory names
    if any(part in _UNWATCHABLE_PARTS for part in resolved.parts):
        return (
            f"Watching a build/cache/virtualenv directory is wasteful and "
            f"exhausts inotify: {path} (should be in exclude_patterns)"
        )

    return None


def validate_watch_paths(paths: list[str]) -> tuple[bool, list[str]]:
    """Validate a list of watch paths before handing them to the observer.

    Args:
        paths: List of directory paths to watch.

    Returns:
        (ok, errors):
          - ok: True if ALL paths are safe to watch recursively.
          - errors: Empty when ok is True; otherwise one clear message per
            offending path (and any validation failure).
    """
    if not paths:
        return False, ["No watch paths provided"]

    errors: list[str] = []
    for raw in paths:
        try:
            p = Path(raw)
        except (TypeError, ValueError) as e:
            errors.append(f"Invalid path {raw!r}: {e}")
            continue

        reason = _classify_reason(p)
        if reason:
            errors.append(reason)

    return (len(errors) == 0), errors


def get_inotify_available() -> int | None:
    """Return the current inotify watch limit, or None if unreadable.

    Reads /proc/sys/fs/inotify/max_user_watches — useful for logging a
    heads-up when approaching the limit. Best-effort, never raises.
    """
    try:
        raw = Path("/proc/sys/fs/inotify/max_user_watches").read_text().strip()
        return int(raw)
    except (OSError, ValueError):
        return None
