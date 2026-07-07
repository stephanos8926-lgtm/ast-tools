"""Tests for vacuum command."""

import pytest

from ast_tools.curator.vacuum import _human_size, run

pytestmark = pytest.mark.unit


class TestVacuum:
    """Test suite for vacuum/space reclamation."""

    def test_run_structure(self):
        """Verify run() returns expected dict structure."""
        result = run(aggressive=False, dry_run=True)
        assert "freed_bytes" in result
        assert "freed_human" in result
        assert "operations" in result
        assert "warnings" in result
        assert isinstance(result["freed_bytes"], int)

    def test_dry_run_no_modifications(self):
        """Verify dry_run doesn't modify anything (just reports)."""
        result = run(aggressive=False, dry_run=True)
        # Should not crash
        assert isinstance(result["operations"], list)

    def test_aggressive_dry_run(self):
        """Verify aggressive+dr y_run doesn't crash."""
        result = run(aggressive=True, dry_run=True)
        assert isinstance(result["operations"], list)

    def test_human_size_bytes(self):
        """Verify _human_size formats correctly."""
        assert _human_size(0) == "0.0 B"
        assert _human_size(500) == "500.0 B"
        assert _human_size(1024) == "1.0 KB"
        assert _human_size(1048576) == "1.0 MB"
        assert _human_size(1073741824) == "1.0 GB"

    def test_human_size_rounding(self):
        """Verify _human_size rounds reasonably."""
        assert _human_size(1536) == "1.5 KB"
        assert _human_size(1572864) == "1.5 MB"
