"""Language routing for LSP server."""

from pathlib import Path

from ast_tools.config.unified import UnifiedConfig
from ast_tools.fix.fixers import get_all_fixers


class LanguageRouter:
    """Maps file URIs to languages and fixers."""

    EXTENSION_MAP = {
        ".py": "python",
        ".js": "javascript", ".jsx": "javascript",
        ".ts": "typescript", ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
        ".c": "c", ".h": "cpp", ".hpp": "cpp",
        ".md": "markdown", ".mdx": "markdown",
    }

    def __init__(self, config: UnifiedConfig):
        self.config = config
        self._fixer_cache: dict[str, list] = {}
        self._build_fixer_map()

    def _build_fixer_map(self):
        """Build language -> fixers map from config."""
        # Get all fixers (built-in + plugins)
        all_fixers = get_all_fixers()

        for lang, fixer_class in all_fixers.items():
            if lang not in self._fixer_cache:
                self._fixer_cache[lang] = []
            self._fixer_cache[lang].append(fixer_class)

        # Add custom fixers from config
        if self.config.plugins and self.config.plugins.custom_fixers:
            for lang, entry_point in self.config.plugins.custom_fixers.items():
                if lang not in self._fixer_cache:
                    self._fixer_cache[lang] = []
                # The plugin system will load these dynamically
                self._fixer_cache[lang].append(("plugin", entry_point))

    def get_language(self, uri: str) -> str:
        """Map file URI to language ID."""
        path = Path(uri.replace("file://", ""))
        return self.EXTENSION_MAP.get(path.suffix.lower(), "python")

    def get_fixers_for_language(self, language: str) -> list:
        """Get all configured fixers for a language."""
        return self._fixer_cache.get(language, [])

    def get_all_languages(self) -> set[str]:
        """Return all supported languages."""
        return set(self._fixer_cache.keys())

    def is_supported(self, uri: str) -> bool:
        """Check if a file is supported."""
        language = self.get_language(uri)
        return language in self._fixer_cache and len(self._fixer_cache[language]) > 0
