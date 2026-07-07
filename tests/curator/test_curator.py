"""Tests for LLM curator service."""

import tempfile
from pathlib import Path

import pytest

from ast_tools.curator.daemon import LLmCurator

pytestmark = pytest.mark.unit


class TestLLmCurator:
    """Test LLM curator functionality."""

    def test_curator_init(self):
        """Test curator initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            curator = LLmCurator(tmpdir)
            assert curator.project_root == Path(tmpdir)

    def test_daily_audit_empty_project(self):
        """Test audit on project with no index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            curator = LLmCurator(tmpdir)
            report = curator.daily_audit()

            assert "timestamp" in report
            assert "health_score" in report
            assert report["total_symbols"] == 0
            assert report["health_score"] == 100.0  # No symbols = no problems

    def test_calculate_health_score(self):
        """Test health score calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            curator = LLmCurator(tmpdir)

            # Perfect health
            score = curator._calculate_health_score(
                total=100, missing_emb=0, contradictions=0, dead=0
            )
            assert score == 100.0

            # Some missing embeddings
            score = curator._calculate_health_score(
                total=100, missing_emb=10, contradictions=0, dead=0
            )
            assert score < 100.0
            assert score > 50.0

            # Many contradictions
            score = curator._calculate_health_score(
                total=100, missing_emb=0, contradictions=20, dead=0
            )
            assert score <= 70.0  # Contradictions penalize heavily

    def test_generate_project_summary(self):
        """Test project summary generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            curator = LLmCurator(tmpdir)

            # Create a fake index
            from ast_tools.database.connection import get_connection

            conn = get_connection(curator.db_path)
            conn.execute("""
                INSERT INTO symbols (id, name, qualified_name, kind, file_path, start_line, end_line, signature, docstring, is_public, content_hash, indexed_at, lang)
                VALUES ('test-1', 'MyClass', 'main.MyClass', 'class', 'main.py', 10, 50, 'class MyClass', 'A test class', 1, 'abc123', strftime('%s','now'), 'python')
            """)
            conn.commit()

            summary = curator.generate_project_summary()

            assert "Project Summary" in summary
            assert "MyClass" in summary
            assert "Architecture" in summary


class TestCuratorTools:
    """Test MCP tool wrappers."""

    def test_curator_audit_tool(self):
        """Test curator_audit MCP tool."""
        from ast_tools.tools.curator import _tool_curator_audit

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _tool_curator_audit({"project_root": tmpdir})

            assert "health_score" in result
            assert "timestamp" in result

    def test_curator_summary_tool(self):
        """Test curator_summary MCP tool."""
        from ast_tools.tools.curator import _tool_curator_summary

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "summary.md")
            result = _tool_curator_summary({"project_root": tmpdir, "output_path": output_path})

            assert "summary" in result
            assert Path(output_path).exists()

    def test_curator_status_tool(self):
        """Test curator_status MCP tool."""
        from ast_tools.tools.curator import _tool_curator_status

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _tool_curator_status({"project_root": tmpdir})

            assert "project_root" in result
            assert "summary_exists" in result
            assert "summary_age_days" in result
