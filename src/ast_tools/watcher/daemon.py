#!/usr/bin/env python3
"""Real-time file watcher for automatic ast-tools reindexing.

Uses watchdog library for cross-platform file system events with debouncing
to automatically reindex files when they change.
"""

import logging
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Lock

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from ..database.connection import get_connection
from ..indexer.extractor import extract_symbols
from ..indexer.parser import parse_source

logger = logging.getLogger(__name__)


class IndexQueue:
    """Thread-safe queue with debouncing for file reindexing.

    Prevents rapid successive reindexing of the same file when an IDE
    writes multiple times during a single save operation.
    """

    def __init__(self, debounce_ms: int = 100):
        """Initialize the queue.

        Args:
            debounce_ms: Milliseconds to wait after last modification before indexing.
        """
        self.queue = deque()
        self.debounce_ms = debounce_ms
        self.last_modified: dict[str, float] = {}
        self.lock = Lock()

    def add(self, file_path: str) -> None:
        """Add a file to the queue for reindexing.

        Args:
            file_path: Absolute path to the file.
        """
        with self.lock:
            now = time.time() * 1000
            self.last_modified[file_path] = now
            if file_path not in self.queue:
                self.queue.append(file_path)
                logger.debug(f"Queued for reindex: {file_path}")

    def remove(self, file_path: str) -> None:
        """Remove a file from the queue (e.g., on deletion).

        Args:
            file_path: Absolute path to the file.
        """
        with self.lock:
            if file_path in self.queue:
                self.queue.remove(file_path)
                self.last_modified.pop(file_path, None)

    def get_ready(self) -> list[str]:
        """Get files ready for indexing (debounce window passed).

        Returns:
            List of file paths ready for reindexing.
        """
        now = time.time() * 1000
        ready = []
        with self.lock:
            to_remove = []
            for path in self.queue:
                if now - self.last_modified.get(path, 0) >= self.debounce_ms:
                    ready.append(path)
                    to_remove.append(path)
            for path in to_remove:
                self.queue.remove(path)
                self.last_modified.pop(path, None)
        return ready

    def size(self) -> int:
        """Get current queue size."""
        with self.lock:
            return len(self.queue)


class AstToolsHandler(FileSystemEventHandler):
    """Watchdog event handler for ast-tools file monitoring.

    Filters events by extension and exclude patterns, then queues
    qualifying files for reindexing.
    """

    def __init__(
        self, queue: IndexQueue, include_extensions: list[str], exclude_patterns: list[str]
    ):
        """Initialize the handler.

        Args:
            queue: IndexQueue for debounced file processing.
            include_extensions: List of file extensions to watch (e.g., ['.py', '.rs']).
            exclude_patterns: List of patterns to exclude (e.g., ['__pycache__', '.git']).
        """
        self.queue = queue
        self.include_extensions = include_extensions
        self.exclude_patterns = exclude_patterns

    def _should_index(self, path: str) -> bool:
        """Check if a file should be indexed.

        Args:
            path: File path to check.

        Returns:
            True if file should be indexed, False otherwise.
        """
        p = Path(path)

        # Check extension
        if p.suffix.lower() not in [ext.lower() for ext in self.include_extensions]:
            return False

        # Check exclude patterns
        path_str = str(p)
        for pattern in self.exclude_patterns:
            # Handle glob patterns
            if "*" in pattern:
                import fnmatch

                if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(p.name, pattern):
                    return False
            else:
                if pattern in path_str:
                    return False

        return True

    def on_modified(self, event) -> None:
        """Handle file modification events."""
        if isinstance(event, FileModifiedEvent) and self._should_index(event.src_path):
            logger.debug(f"File modified: {event.src_path}")
            self.queue.add(event.src_path)

    def on_created(self, event) -> None:
        """Handle file creation events."""
        if isinstance(event, FileCreatedEvent) and self._should_index(event.src_path):
            logger.debug(f"File created: {event.src_path}")
            self.queue.add(event.src_path)

    def on_deleted(self, event) -> None:
        """Handle file deletion events."""
        if isinstance(event, FileDeletedEvent) and self._should_index(event.src_path):
            logger.debug(f"File deleted: {event.src_path}")
            # Mark for removal from index
            self.queue.remove(event.src_path)

    def on_moved(self, event) -> None:
        """Handle file move events."""
        if isinstance(event, FileMovedEvent):
            # Handle source if it was a tracked file
            if self._should_index(event.src_path):
                self.queue.remove(event.src_path)
            # Handle destination if it should be tracked
            if self._should_index(event.dest_path):
                self.queue.add(event.dest_path)


class WatcherDaemon:
    """Main watcher daemon for real-time file monitoring.

    Monitors specified paths for file changes and triggers automatic
    reindexing via a callback function.
    """

    def __init__(
        self,
        watch_paths: list[str],
        include_extensions: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        debounce_ms: int = 100,
    ):
        """Initialize the watcher daemon.

        Args:
            watch_paths: List of directories to watch.
            include_extensions: Extensions to include (default: common code files).
            exclude_patterns: Patterns to exclude (default: common build/cache dirs).
            debounce_ms: Debounce window in milliseconds.
        """
        self.watch_paths = [str(Path(p).resolve()) for p in watch_paths]
        self.include_extensions = include_extensions or [
            ".py",
            ".rs",
            ".go",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".java",
            ".rb",
            ".php",
            ".json",
            ".yaml",
            ".yml",
            ".sh",
            ".bash",
            ".md",
        ]
        self.exclude_patterns = exclude_patterns or [
            "__pycache__",
            ".git",
            "node_modules",
            "venv",
            ".venv",
            "*.log",
            "*.tmp",
            ".DS_Store",
            ".egg-info",
            "dist",
            "build",
        ]
        self.queue = IndexQueue(debounce_ms=debounce_ms)
        self.observer: Observer | None = None
        self.handler: AstToolsHandler | None = None
        self.running = False

    def start(self) -> None:
        """Start watching all paths."""
        self.handler = AstToolsHandler(self.queue, self.include_extensions, self.exclude_patterns)
        self.observer = Observer()
        for path in self.watch_paths:
            self.observer.schedule(self.handler, path, recursive=True)
        self.observer.start()
        self.running = True
        logger.info(f"Watcher started: monitoring {len(self.watch_paths)} paths")

    def stop(self) -> None:
        """Stop watching."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None
        self.running = False
        logger.info("Watcher stopped")

    def run(self, reindex_callback: Callable[[str], None] | None = None) -> None:
        """Main loop - runs until interrupted.

        Args:
            reindex_callback: Function to call with file paths ready for reindexing.
        """
        self.start()
        try:
            while self.running:
                time.sleep(1)
                # Check queue for ready files
                ready = self.queue.get_ready()
                if ready and reindex_callback:
                    for path in ready:
                        logger.info(f"Reindexing: {path}")
                        reindex_callback(path)
        except KeyboardInterrupt:
            logger.info("Received interrupt, stopping watcher...")
            self.stop()

    def get_status(self) -> dict:
        """Get watcher status information.

        Returns:
            Dict with running state, paths, and queue size.
        """
        return {
            "running": self.running,
            "paths": self.watch_paths,
            "queue_size": self.queue.size() if self.queue else 0,
            "extensions": self.include_extensions,
            "excludes": self.exclude_patterns,
        }


def reindex_file(file_path: str) -> dict:
    """Callback to reindex a single file via ast-tools API.

    Args:
        file_path: Path to the file to reindex.

    Returns:
        Dict with status and symbol count.
    """
    try:
        # Read and parse file
        p = Path(file_path)
        if not p.exists():
            return {"status": "error", "path": file_path, "error": "File not found"}

        content = p.read_text(encoding="utf-8", errors="ignore")
        result = parse_source(content, file_path)

        if not result.success:
            logger.error(f"Parse failed for {file_path}: {result.error}")
            return {"status": "error", "path": file_path, "error": result.error}

        # Extract symbols
        symbols, _edges = extract_symbols(result.tree, file_path)

        # Update database
        with get_connection() as conn:
            cursor = conn.cursor()

            # Delete old symbols for this file
            cursor.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))

            # Insert new symbols
            for symbol in symbols:
                cursor.execute(
                    """
                    INSERT INTO symbols (
                        id, name, qualified_name, kind, file_path,
                        start_line, end_line, signature, docstring,
                        is_public, content_hash, indexed_at, lang
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        symbol.id,
                        symbol.name,
                        symbol.qualified_name,
                        symbol.kind.value if hasattr(symbol.kind, "value") else str(symbol.kind),
                        symbol.file_path,
                        symbol.start_line,
                        symbol.end_line,
                        symbol.signature,
                        symbol.docstring,
                        1 if symbol.is_public else 0,
                        symbol.content_hash or "",
                        int(datetime.now().timestamp()),
                        symbol.lang if hasattr(symbol, "lang") and symbol.lang else "python",
                    ),
                )

            conn.commit()

        logger.info(f"✓ Reindexed {file_path} ({len(symbols)} symbols)")
        return {"status": "success", "path": file_path, "symbol_count": len(symbols)}

    except Exception as e:
        logger.error(f"✗ Failed to reindex {file_path}: {e}")
        return {"status": "error", "path": file_path, "error": str(e)}


# CLI entry point
if __name__ == "__main__":
    import signal
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Parse watch paths from args or use current directory
    watch_paths = sys.argv[1:] if len(sys.argv) > 1 else ["."]

    daemon = WatcherDaemon(watch_paths)

    # Graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    daemon.run(reindex_callback=reindex_file)
