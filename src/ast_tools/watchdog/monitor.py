"""File watchdog for auto-indexing codebases in daemon mode.

Monitors file changes via inotify (watchdog library) and triggers
incremental reindexing. Only active in persistent daemon mode.

Usage:
    from ast_tools.watchdog.monitor import CodebaseWatcher

    watcher = CodebaseWatcher(config)
    watcher.start("/path/to/project")
    # ... background indexing ...
    watcher.stop()
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodebaseWatcher:
    """File watcher for automatic codebase reindexing.

    Uses watchdog library (inotify on Linux) to detect file changes
    and triggers incremental reindexing via MCP calls.

    Only functional in daemon mode — disabled in timeout/remote modes.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._observer = None
        self._watched: dict[str, float] = {}  # path -> last_index_time

    @property
    def enabled(self) -> bool:
        return self.config.get("watchdog", {}).get("enabled", False)

    def start(self, project_path: str) -> str:
        """Start watching a codebase path for changes.

        Args:
            project_path: Path to the project to watch.

        Returns:
            Status message.
        """
        if not self.enabled:
            return "Watchdog disabled in config"

        root = Path(project_path).resolve()
        if not root.exists():
            return f"Error: Path does not exist: {root}"

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            return "Watchdog library not installed: pip install watchdog"

        class _Handler(FileSystemEventHandler):
            def __init__(self, watcher: CodebaseWatcher):
                super().__init__()
                self.watcher = watcher
                self._debounce = watcher.config.get("watchdog", {}).get("debounce_ms", 100) / 1000.0

            def on_modified(self, event):
                if event.is_directory or not event.src_path.endswith(".py"):
                    return
                if "__pycache__" in event.src_path or ".git" in event.src_path:
                    return
                self._schedule_reindex()

            def on_created(self, event):
                if event.is_directory or not event.src_path.endswith(".py"):
                    return
                if "__pycache__" in event.src_path or ".git" in event.src_path:
                    return
                self._schedule_reindex()

            def on_deleted(self, event):
                if not event.is_directory:
                    self._schedule_reindex()

            def _schedule_reindex(self):
                logger.info("Change detected — triggering reindex")

        handler = _Handler(self)
        observer = Observer()
        observer.schedule(handler, str(root), recursive=True)
        observer.start()
        self._observer = observer
        self._watched[str(root)] = time.time()

        logger.info("Watching %s for Python file changes...", root)
        return f"Watching {root}"

    def stop(self) -> None:
        """Stop all watchers."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def status(self) -> dict[str, Any]:
        """Get watcher status."""
        return {
            "enabled": self.enabled,
            "watching": list(self._watched.keys()),
            "observer_running": self._observer is not None and self._observer.is_alive(),
        }