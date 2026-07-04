"""Tests for cleanup command."""

from pathlib import Path

from ast_tools.curator.cleanup import run, _human_size


import pytest
pytestmark = pytest.mark.integration

class TestCleanup:
    """Test suite for cleanup command."""

    def test_run_structure(self):
        """Verify run() returns expected dict structure."""
        result = run(aggressive=False, dry_run=True)
        assert "freed_bytes" in result
        assert "freed_human" in result
        assert "operations" in result
        assert "warnings" in result

    def test_dry_run_no_modifications(self):
        """Verify dry_run doesn't crash."""
        result = run(aggressive=False, dry_run=True)
        assert isinstance(result["freed_bytes"], int)

    def test_aggressive_dry_run(self):
        """Verify aggressive+dry_run doesn't crash."""
        result = run(aggressive=True, dry_run=True)
        assert isinstance(result["operations"], list)

    def test_human_size(self):
        """Verify _human_size formats correctly."""
        assert _human_size(0) == "0.0 B"
        assert _human_size(500) == "500.0 B"
        assert _human_size(1024) == "1.0 KB"
        assert _human_size(1048576) == "1.0 MB"

    def test_human_size_rounding(self):
        """Verify _human_size rounds."""
        assert _human_size(1536) == "1.5 KB"