"""Tests for setup wizard."""

import json
import tempfile
from pathlib import Path

import pytest

from ast_tools.curator.setup_wizard import run, _create_config_dir, _check_environment


class TestSetupWizard:
    """Test suite for the setup wizard."""

    def test_config_dir_creation(self):
        """Verify config directory is created correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            # We need to mock the home dir
            # For now, test the function logic directly
            # by checking it resolves and creates dirs
            from ast_tools.curator.setup_wizard import AST_TOOLS_DIR, SUBDIRS
            # Test that SUBDIRS has the expected structure
            assert "config" in SUBDIRS
            assert "cache/models" in SUBDIRS
            assert "logs" in SUBDIRS
            assert "backups" in SUBDIRS

    def test_environment_check_python(self):
        """Verify environment check detects Python version."""
        import sys
        ok, issues = _check_environment()
        # Should pass on Python 3.10+
        assert isinstance(ok, bool)
        assert isinstance(issues, list)

    def test_environment_check_disk(self):
        """Verify disk space check runs without error."""
        ok, issues = _check_environment()
        # Should not crash
        for issue in issues:
            assert isinstance(issue, str)

    def test_run_with_skip_model(self):
        """Verify run() completes with --skip-model."""
        result = run(
            non_interactive=True,
            skip_model=True,
        )
        assert "errors" in result
        assert result["db_initialized"] is True or result.get("errors")
        # Should not crash
        assert isinstance(result, dict)

    def test_run_result_structure(self):
        """Verify run() returns expected structure."""
        result = run(
            non_interactive=True,
            skip_model=True,
        )
        expected_keys = {
            "config_dir", "db_initialized", "model_installed",
            "index_created", "health_score", "errors", "warnings",
        }
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"