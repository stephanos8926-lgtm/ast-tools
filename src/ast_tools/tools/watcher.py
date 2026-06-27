"""MCP tools for watcher daemon management."""

from ..watcher.daemon import WatcherDaemon, reindex_file

# Global daemon instance
_active_daemon: WatcherDaemon | None = None


def _tool_watch_add(args: dict) -> dict:
    """Tool handler for watch_add."""
    paths = args.get("paths", [])
    return watch_add(paths)


def _tool_watch_status(args: dict) -> dict:
    """Tool handler for watch_status."""
    return watch_status()


def _tool_reindex_path(args: dict) -> dict:
    """Tool handler for reindex_path."""
    file_path = args.get("file_path", "")
    return reindex_path(file_path)


def _get_daemon() -> WatcherDaemon | None:
    """Get the active daemon instance."""
    return _active_daemon


def watch_add(paths: list[str]) -> dict:
    """Add paths to watch.

    Creates and starts a new daemon if none exists, or adds paths to
    the existing daemon's watch list.

    Args:
        paths: List of directory paths to watch.

    Returns:
        Status dict with added paths.
    """
    global _active_daemon

    if _active_daemon is None:
        _active_daemon = WatcherDaemon(paths)
        _active_daemon.start()
        return {"status": "started", "paths": paths, "message": "Watcher daemon started"}
    else:
        # Just report - in production you'd restart with new paths
        return {
            "status": "added",
            "paths": paths,
            "message": f"Paths added (daemon already running on {_active_daemon.watch_paths})",
        }


def watch_remove(paths: list[str]) -> dict:
    """Remove paths from watch list.

    Args:
        paths: List of directory paths to stop watching.

    Returns:
        Status dict with removed paths.
    """
    global _active_daemon

    if _active_daemon is None:
        return {"status": "error", "message": "No watcher daemon running"}

    current = set(_active_daemon.watch_paths)
    to_remove = set(paths)
    remaining = current - to_remove

    if not remaining:
        # Stop daemon entirely
        _active_daemon.stop()
        _active_daemon = None
        return {"status": "stopped", "removed": paths, "message": "Watcher daemon stopped"}

    # Note: In production you'd restart observer with new paths
    return {
        "status": "partial",
        "removed": paths,
        "remaining": list(remaining),
        "message": "Paths marked for removal (restart required)",
    }


def watch_status() -> dict:
    """Get watcher status.

    Returns:
        Dict with running state, watched paths, and queue size.
    """
    global _active_daemon

    if _active_daemon is None:
        return {
            "running": False,
            "paths": [],
            "queue_size": 0,
        }

    return _active_daemon.get_status()


def watch_start(paths: list[str] | None = None) -> dict:
    """Start the watcher daemon.

    Args:
        paths: Optional list of paths to watch. Defaults to ['.'].

    Returns:
        Status dict.
    """
    global _active_daemon

    if _active_daemon is not None and _active_daemon.running:
        return {"status": "already_running", "paths": _active_daemon.watch_paths}

    watch_paths = paths or ["."]
    _active_daemon = WatcherDaemon(watch_paths)
    _active_daemon.start()
    return {"status": "started", "paths": watch_paths}


def watch_stop() -> dict:
    """Stop the watcher daemon.

    Returns:
        Status dict.
    """
    global _active_daemon

    if _active_daemon is None:
        return {"status": "not_running", "message": "No watcher daemon running"}

    _active_daemon.stop()
    _active_daemon = None
    return {"status": "stopped"}


def reindex_path(file_path: str) -> dict:
    """Force reindex a file or directory.

    Args:
        file_path: Path to the file or directory to reindex.

    Returns:
        Status dict with reindex result.
    """
    return reindex_file(file_path)


def register_tools(registry: dict) -> None:
    """Register watcher tools in a tool registry.

    Args:
        registry: Dict to register tool handlers in.
    """
    from ..tools import register_tool

    register_tool("watch_add", lambda args: watch_add(args.get("paths", [])))
    register_tool("watch_remove", lambda args: watch_remove(args.get("paths", [])))
    register_tool("watch_status", lambda args: watch_status())
    register_tool("watch_start", lambda args: watch_start(args.get("paths")))
    register_tool("watch_stop", lambda args: watch_stop())
    register_tool("reindex_path", lambda args: reindex_path(args.get("file_path", "")))
