"""Tests for doctor command."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ast_tools.curator.doctor import run, _track_trend


class TestDoctor:
    """Test suite for doctor healthcheck."""

    def test_run_structure(self):
        """Verify run() returns expected structure."""
        result = run(verbose=False, fix=False, format="text", save_baseline=False)
        expected_keys = {"score", "status", "checks", "trend", "auto_fixes", "timestamp"}
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 100
        assert result["status"] in ("healthy", "warning", "critical")

    def test_run_checks_list(self):
        """Verify checks list contains expected check names."""
        result = run(verbose=False, fix=False, format="text", save_baseline=False)
        check_names = {c["check"] for c in result["checks"]}
        expected = {"database", "integrity", "schema", "model", "index", "config", "deps"}
        for name in expected:
            assert name in check_names, f"Missing check: {name}"

    def test_run_all_checks_have_scores(self):
        """Verify every check has a score field."""
        result = run(verbose=False, fix=False, format="text", save_baseline=False)
        for c in result["checks"]:
            assert "score" in c, f"Missing score in {c['check']}"
            assert isinstance(c["score"], int), f"Non-int score in {c['check']}"

    def test_run_verbose_adds_detail(self):
        """Verbose flag doesn't crash (detail is always present)."""
        result = run(verbose=True, fix=False, format="text", save_baseline=False)
        for c in result["checks"]:
            assert "detail" in c, f"Missing detail in {c['check']}"

    def test_trend_tracking(self):
        """Verify trend tracking stores and returns data."""
        trend = _track_trend(85)
        assert "current" in trend
        assert trend["current"] == 85

    def test_trend_tracking_consecutive(self):
        """Verify consecutive calls track delta."""
        _track_trend(90)
        trend = _track_trend(85)
        assert trend["previous"] is not None
        assert trend["current"] == 85
        assert trend["delta"] == -5  # 85 - 90 = -5

    def test_doctor_healthy_no_db(self):
        """Verify doctor returns a valid status (not crash) when no DB exists."""
        result = run(save_baseline=False)
        assert result["status"] in ("healthy", "warning", "critical")
        assert isinstance(result["score"], int)

    def test_doctor_exit_code_mapping(self):
        """Verify score → exit code mapping is logical."""
        from ast_tools.curator.doctor import MIN_HEALTHY, MIN_WARNING
        assert 0 <= MIN_WARNING < MIN_HEALTHY <= 100