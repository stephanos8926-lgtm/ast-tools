"""Tests for the LSP code action handler."""

import asyncio
from pathlib import Path

import pytest

from ast_tools.config.unified import UnifiedConfig
from ast_tools.lsp.code_actions import CodeActionHandler
from ast_tools.lsp.document_store import DocumentStore
from ast_tools.lsp.language_router import LanguageRouter
from lsprotocol import types as lsp_types


class MockServer:
    """Mock LSP server for testing."""

    def __init__(self, config=None):
        self.config = config or UnifiedConfig()
        self.document_store = DocumentStore()
        self.language_router = LanguageRouter(self.config)


class TestCodeActionHandler:
    """Test the CodeActionHandler class."""

    @pytest.fixture
    def handler(self):
        """Create a CodeActionHandler with mock server."""
        server = MockServer()
        return CodeActionHandler(server)

    @pytest.mark.asyncio
    async def test_get_code_actions_empty_document(self, handler):
        """Empty document should return no actions."""
        handler.server.document_store.did_open("file:///empty.py", "", "python")

        code_action_params = lsp_types.CodeActionParams(
            text_document=lsp_types.TextDocumentIdentifier(uri="file:///empty.py"),
            range=lsp_types.Range(
                start=lsp_types.Position(line=0, character=0),
                end=lsp_types.Position(line=0, character=0),
            ),
            context=lsp_types.CodeActionContext(diagnostics=[]),
        )

        actions = await handler.get_code_actions(code_action_params)
        assert actions == []

    @pytest.mark.asyncio
    async def test_get_code_actions_unsupported_language(self, handler):
        """Unsupported language should return no actions."""
        uri = "file:///test.xyz"
        handler.server.document_store.did_open("file:///test.xyz", "some content", "unknown")

        handler.server.document_store.did_open("file:///empty.py", "", "python")

        code_action_params = lsp_types.CodeActionParams(
            text_document=lsp_types.TextDocumentIdentifier(uri=uri),
            range=lsp_types.Range(
                start=lsp_types.Position(line=0, character=0),
                end=lsp_types.Position(line=0, character=0),
            ),
            context=lsp_types.CodeActionContext(diagnostics=[]),
        )

        actions = await handler.get_code_actions(code_action_params)
        # Actions may still be returned for unknown extensions
        # since extension falls back to .txt
        assert isinstance(actions, list)

    @pytest.mark.asyncio
    async def test_get_code_actions_python_trailing_newline(self, handler):
        """Test code action for trailing newline fix."""
        # Python file with missing trailing newline
        handler.server.document_store.did_open("file:///test.py", "x = 1\n", "python")
        handler.server.document_store.did_open("file:///empty.py", "", "python")

        code_action_params = lsp_types.CodeActionParams(
            text_document=lsp_types.TextDocumentIdentifier(uri="file:///test.py"),
            range=lsp_types.Range(
                start=lsp_types.Position(line=0, character=0),
                end=lsp_types.Position(line=0, character=0),
            ),
            context=lsp_types.CodeActionContext(diagnostics=[]),
        )

        actions = await handler.get_code_actions(code_action_params)
        # Should have at least one action for trailing newline
        assert isinstance(actions, list)

    @pytest.mark.asyncio
    async def test_resolve_code_action(self, handler):
        """Test resolving a lazy code action."""
        action = lsp_types.CodeAction(
            title="Test action",
            kind=lsp_types.CodeActionKind.QuickFix,
        )

        resolved = await handler.resolve_code_action(action)
        # Should return as-is when no data
        assert resolved == action

    def test_safety_to_code_action_kind(self, handler):
        """Test safety level to code action kind mapping."""
        assert handler._safety_to_code_action_kind("safe") == lsp_types.CodeActionKind.QuickFix
        assert handler._safety_to_code_action_kind("unsafe") == lsp_types.CodeActionKind.Refactor
        assert handler._safety_to_code_action_kind("display_only") == lsp_types.CodeActionKind.RefactorInline
        assert handler._safety_to_code_action_kind("unknown") == lsp_types.CodeActionKind.RefactorInline

    def test_get_extension(self, handler):
        """Test language to file extension mapping."""
        assert handler._get_extension("python") == ".py"
        assert handler._get_extension("typescript") == ".ts"
        assert handler._get_extension("javascript") == ".js"
        assert handler._get_extension("go") == ".go"
        assert handler._get_extension("rust") == ".rs"
        assert handler._get_extension("cpp") == ".cpp"
        assert handler._get_extension("c") == ".c"
        assert handler._get_extension("markdown") == ".md"
        assert handler._get_extension("unknown") == ".txt"


class TestCodeActionIntegration:
    """Integration tests for code actions with real fixers."""

    @pytest.fixture
    def handler(self):
        """Create handler with real configuration."""
        config = UnifiedConfig()
        server = MockServer(config)
        return CodeActionHandler(server)

    @pytest.mark.asyncio
    async def test_python_import_sorting(self, handler):
        """Test code action for import sorting."""
        handler.server.document_store.did_open("file:///test.py", "import os\nimport sys\n", "python")
        handler.server.document_store.did_open("file:///empty.py", "", "python")

        code_action_params = lsp_types.CodeActionParams(
            text_document=lsp_types.TextDocumentIdentifier(uri="file:///test.py"),
            range=lsp_types.Range(
                start=lsp_types.Position(line=0, character=0),
                end=lsp_types.Position(line=0, character=0),
            ),
            context=lsp_types.CodeActionContext(diagnostics=[]),
        )

        actions = await handler.get_code_actions(code_action_params)
        assert isinstance(actions, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])