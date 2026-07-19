import asyncio
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ast_tools.config.unified import load_unified_config

if TYPE_CHECKING:
    from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    """Handles file system events for config files."""

    def __init__(self, callback):
        self.callback = callback
        self._last_event_time = 0.0

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return

        path = Path(event.src_path)
        # Only react to config files
        if path.name in ("ast-tools.yaml", "pyproject.toml", ".ast-tools.yaml"):
            # Debounce: ignore events within 500ms of each other
            now = time.time()
            if now - self._last_event_time < 0.5:
                return
            self._last_event_time = now

            logger.info(f"Config file changed: {path}")
            asyncio.create_task(self.callback(path))


class ConfigWatcher:
    """Watches config files for changes, triggers hot-reload."""

    def __init__(self, server):
        self.server = server
        self.observer: Observer | None = None
        self._watched_paths: set[Path] = set()

    async def start(self):
        """Begin watching config files in workspace folders."""
        if self.observer:
            return

        self.observer = Observer()
        handler = ConfigFileHandler(self._on_config_change)

        # Watch workspace folders
        for folder in self.server._workspace_folders:
            path = Path(folder.uri.replace("file://", ""))
            if path.exists() and path not in self._watched_paths:
                self.observer.schedule(handler, str(path), recursive=True)
                self._watched_paths.add(path)
                logger.info(f"Watching config files in: {path}")

        # Also watch user config dir
        from ast_tools.config.loader import get_config_dir
        user_config = get_config_dir()
        if user_config.exists() and user_config not in self._watched_paths:
            self.observer.schedule(handler, str(user_config), recursive=False)
            self._watched_paths.add(user_config)

        self.observer.start()
        logger.info("Config watcher started")

    async def stop(self):
        """Stop watching."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None
            logger.info("Config watcher stopped")

    async def _on_config_change(self, path: Path):
        """Reload config and reinitialize components."""
        logger.info(f"Reloading configuration from {path}")

        try:
            # Reload unified config
            workspace_root = None
            if self.server._workspace_folders:
                workspace_root = Path(self.server._workspace_folders[0].uri.replace("file://", ""))

            pyproject_path = workspace_root / "pyproject.toml" if workspace_root else None
            yaml_path = workspace_root / "ast-tools.yaml" if workspace_root else None

            # Also check user config dir
            from ast_tools.config.loader import get_config_dir
            user_yaml = get_config_dir() / "ast-tools.yaml"

            cli_overrides = {"lsp": {"enabled": True}}
            self.server.config = load_unified_config(
                pyproject_path=pyproject_path if pyproject_path and pyproject_path.exists() else None,
                yaml_path=yaml_path if yaml_path and yaml_path.exists() else None,
                cli_overrides=cli_overrides,
            )

            # Reinitialize components that depend on config
            from .language_router import LanguageRouter
            self.server.language_router = LanguageRouter(self.server.config)

            # Recreate fix engine with new plugin fixers
            plugin_fixers = self.server.config.plugins.custom_fixers if self.server.config.plugins else {}
            from ast_tools.fix.config import FixConfig
            from ast_tools.fix.engine import FixContext, FixEngine, SafetyLevel

            level_map = {
                "safe": SafetyLevel.SAFE,
                "unsafe": SafetyLevel.UNSAFE,
                "display_only": SafetyLevel.DISPLAY_ONLY,
            }
            safety_level = level_map.get(self.server.config.fix.safety_level, SafetyLevel.SAFE)

            context = FixContext(
                project_root=Path(".").resolve(),
                target_paths=[Path(".").resolve()],
                languages=set(self.server.language_router.get_all_languages()),
                config=FixConfig(),
                safety_level=safety_level,
                check_only=False,
                diff_only=False,
                verbose=False,
                max_iterations=self.server.config.fix.max_iterations,
            )
            self.server.fix_engine = FixEngine(context, plugin_fixers=plugin_fixers)

            logger.info("Configuration reloaded successfully")

        except Exception as e:
            logger.error(f"Failed to reload config: {e}", exc_info=True)
