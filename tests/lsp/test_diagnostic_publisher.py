"""Unit tests for the LSP diagnostic publisher."""

import hashlib
from unittest.mock import AsyncMock, Mock, patch

import pytest
from lsprotocol import types as lsp_types

from ast_tools.config.unified import DiagnosticConfig
from ast_tools.fix.fixers import FixAction
from ast_tools.lsp.diagnostic_publisher import DiagnosticPublisher


@pytest.fixture
def diagnostic_config():
    return DiagnosticConfig(
        enabled=True,
        debounce_ms=100,
        max_diagnostics_per_file=50,
        push_diagnostics=True,
        pull_diagnostics=False,
        include_related_information=True,
    )


@pytest.fixture
def mock_server():
    """Create a mock LSP server."""
    server = Mock()
    server.publish_diagnostics = AsyncMock()
    server.language_router = Mock()
    server.language_router.get_fixers_for_language.return_value = []
    server.config.lsp.diagnostics = DiagnosticConfig()
    server._get_safety_level = Mock(return_value="safe")
    server.language_router.get_language.return_value = "python"
    return server


class TestDiagnosticPublisher:
    """Test the DiagnosticPublisher class."""

    def test_init(self, mock_server, diagnostic_config):
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        assert publisher.config == diagnostic_config
        assert publisher.server == mock_server

    def test_safety_to_severity_safe(self, mock_server, diagnostic_config):
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        assert publisher._safety_to_severity("safe") == lsp_types.DiagnosticSeverity.Information

    def test_safety_to_severity_unsafe(self, mock_server, diagnostic_config):
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        assert publisher._safety_to_severity("unsafe") == lsp_types.DiagnosticSeverity.Warning

    def test_safety_to_severity_display_only(self, mock_server, diagnostic_config):
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        assert publisher._safety_to_severity("display_only") == lsp_types.DiagnosticSeverity.Hint

    def test_get_extension(self, mock_server, diagnostic_config):
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        assert publisher._get_extension("python") == ".py"
        assert publisher._get_extension("typescript") == ".ts"
        assert publisher._get_extension("go") == ".go"
        assert publisher._get_extension("rust") == ".rs"
        assert publisher._get_extension("nonexistent") == ".txt"

    def test_hash_diagnostics_empty(self, mock_server, diagnostic_config):
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        h = publisher._hash_diagnostics([])
        assert isinstance(h, str)
        assert len(h) == 32  # md5

    def test_hash_diagnostics_deterministic(self, mock_server, diagnostic_config):
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        diag1 = lsp_types.Diagnostic(
            range=lsp_types.Range(
                start=lsp_types.Position(line=0, character=0),
                end=lsp_types.Position(line=1, character=0),
            ),
            message="test error",
            severity=lsp_types.DiagnosticSeverity.Error,
        )
        h1 = publisher._hash_diagnostics([diag1])
        h2 = publisher._hash_diagnostics([diag1])
        assert h1 == h2

    def test_hash_diagnostics_different(self, mock_server, diagnostic_config):
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        diag1 = lsp_types.Diagnostic(
            range=lsp_types.Range(
                start=lsp_types.Position(line=0, character=0),
                end=lsp_types.Position(line=1, character=0),
            ),
            message="test error",
        )
        diag2 = lsp_types.Diagnostic(
            range=lsp_types.Range(
                start=lsp_types.Position(line=0, character=0),
                end=lsp_types.Position(line=1, character=0),
            ),
            message="different error",
        )
        assert publisher._hash_diagnostics([diag1]) != publisher._hash_diagnostics([diag2])

    def test_fix_action_diagnostic_conversion(self, mock_server, diagnostic_config):
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        from pathlib import Path
        
        action = FixAction(
            tool="ruff",
            file_path=Path("/project/main.py"),
            description="Remove unused import 'os'",
            original_content="import os\nx = 1\n",
            fixed_content="x = 1\n",
            safety="safe",
            metadata={
                "rule_code": "F401",
                "start_pos": (0, 0),
                "end_pos": (0, 11),
            },
        )
        
        diagnostics = publisher._fix_actions_to_diagnostics([action], "python", "import os\nx = 1\n")
        assert len(diagnostics) == 1
        
        d = diagnostics[0]
        assert d.message == "Remove unused import 'os'"
        assert d.severity == lsp_types.DiagnosticSeverity.Information
        assert d.code == "F401"
        assert d.source == "ast-tools.ruff"
        assert d.data["fixer"] == "ruff"
        assert d.data["fixable"] is True
        
        # Check range
        assert d.range.start.line == 0
        assert d.range.start.character == 0
        assert d.range.end.line == 0
        assert d.range.end.character == 11
        
        # Check tags for "unused"
        assert d.tags == [lsp_types.DiagnosticTag.Unnecessary]

    def test_fix_action_without_metadata(self, mock_server, diagnostic_config):
        """Test diagnostic conversion when no position metadata."""
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        from pathlib import Path
        
        action = FixAction(
            tool="ruff",
            file_path=Path("/project/main.py"),
            description="Extra trailing newlines",
            original_content="x = 1\n\n\n",
            fixed_content="x = 1\n",
            safety="safe",
            metadata={},  # No position info
        )
        
        diagnostics = publisher._fix_actions_to_diagnostics([action], "python", "x = 1\n\n\n")
        assert len(diagnostics) == 1
        
        # Should use _locate_change to find position
        d = diagnostics[0]
        # The change is at line 1 (the extra blank lines)
        assert d.message == "Extra trailing newlines"

    def test_locate_change_same_content(self, mock_server, diagnostic_config):
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        start, end = publisher._locate_change("x = 1\n", "x = 1\n", "x = 42\n")
        # Change at line 0
        assert start[0] == 0
        assert end[0] == 0

    def test_disabled_publisher(self, mock_server):
        config = DiagnosticConfig(enabled=False)
        publisher = DiagnosticPublisher(mock_server, config)
        
        import asyncio
        diagnostics = asyncio.run(publisher.compute_diagnostics("file:///test.py", "x = 1", "python"))
        assert diagnostics == []

    @pytest.mark.asyncio
    async def test_publish_diagnostics_empty(self, mock_server, diagnostic_config):
        """Test that publishing with no fixers produces empty diagnostics."""
        publisher = DiagnosticPublisher(mock_server, diagnostic_config)
        server = mock_server
        server.language_router.get_fixers_for_language.return_value = []
        
        result = await publisher.compute_diagnostics(
            "file:///test.py", "x = 1\n", "python"
        )
        assert result == []