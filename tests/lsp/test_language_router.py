"""Unit tests for the LSP language router."""

from pathlib import Path

import pytest

from ast_tools.config.unified import UnifiedConfig
from ast_tools.lsp.language_router import LanguageRouter


@pytest.fixture
def router():
    """Create a LanguageRouter with default config."""
    config = UnifiedConfig()
    return LanguageRouter(config)


class TestLanguageRouter:
    """Test the LanguageRouter class."""

    def test_get_language_python(self, router):
        assert router.get_language("file:///project/main.py") == "python"
        assert router.get_language("file:///project/lib/module.py") == "python"

    def test_get_language_typescript(self, router):
        assert router.get_language("file:///project/main.ts") == "typescript"
        assert router.get_language("file:///project/component.tsx") == "typescript"

    def test_get_language_javascript(self, router):
        assert router.get_language("file:///project/main.js") == "javascript"
        assert router.get_language("file:///project/component.jsx") == "javascript"

    def test_get_language_go(self, router):
        assert router.get_language("file:///project/main.go") == "go"

    def test_get_language_rust(self, router):
        assert router.get_language("file:///project/main.rs") == "rust"

    def test_get_language_cpp(self, router):
        assert router.get_language("file:///project/main.cpp") == "cpp"
        assert router.get_language("file:///project/main.cc") == "cpp"
        assert router.get_language("file:///project/header.h") == "cpp"

    def test_get_language_markdown(self, router):
        assert router.get_language("file:///project/README.md") == "markdown"
        assert router.get_language("file:///project/docs.mdx") == "markdown"

    def test_get_language_unknown_default(self, router):
        assert router.get_language("file:///project/file.xyz") == "python"
        assert router.get_language("file:///project/Makefile") == "python"

    def test_get_all_languages(self, router):
        languages = router.get_all_languages()
        assert "python" in languages
        assert "typescript" in languages
        assert "go" in languages
        assert "rust" in languages
        assert "cpp" in languages
        assert "markdown" in languages

    def test_is_supported_python(self, router):
        assert router.is_supported("file:///project/main.py") is True

    def test_is_supported_unknown(self, router):
        # Depends on whether default language has fixers
        result = router.is_supported("file:///project/file.xyz")
        assert isinstance(result, bool)

    def test_get_fixers_for_language(self, router):
        python_fixers = router.get_fixers_for_language("python")
        assert len(python_fixers) > 0

        go_fixers = router.get_fixers_for_language("go")
        assert len(go_fixers) > 0

    def test_get_fixers_for_nonexistent(self, router):
        fixers = router.get_fixers_for_language("nonexistent")
        assert fixers == []

    def test_router_with_custom_fixers(self):
        """Test router with custom fixer plugins configured."""
        config = UnifiedConfig()
        config.plugins.custom_fixers["sql"] = "some.module:SQLFixer"
        router = LanguageRouter(config)
        sql_fixers = router.get_fixers_for_language("sql")
        # Should have plugin entry even though module doesn't exist
        # (errors are silently handled)
        assert len(sql_fixers) == 1

    def test_case_sensitivity(self, router):
        assert router.get_language("file:///project/main.PY") == "python"
        assert router.get_language("file:///project/main.TS") == "typescript"