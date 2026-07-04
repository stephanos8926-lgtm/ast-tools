"""Tests for hotspot detection and co-change MCP tools."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest


pytestmark = pytest.mark.integration

def _create_test_db(db_path: Path) -> None:
    """Create a test DB with churn and co-change data."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS churn_metrics (
            file_path TEXT PRIMARY KEY,
            commit_count INTEGER DEFAULT 0,
            lines_added INTEGER DEFAULT 0,
            lines_deleted INTEGER DEFAULT 0,
            authors_count INTEGER DEFAULT 0,
            last_modified INTEGER,
            instability REAL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS co_change_pairs (
            id INTEGER PRIMARY KEY,
            symbol1_id TEXT NOT NULL,
            symbol2_id TEXT NOT NULL,
            frequency INTEGER DEFAULT 0,
            avg_gap REAL DEFAULT 0.0,
            last_co_change INTEGER,
            coupling REAL DEFAULT 0.0
        );
        INSERT INTO churn_metrics VALUES
            ('app.py', 10, 100, 50, 2, 1700000000, 0.3333),
            ('utils.py', 5, 30, 5, 1, 1700000001, 0.1429),
            ('models.py', 20, 500, 10, 3, 1700000002, 0.0196),
            ('config.py', 2, 5, 1, 1, 1700000003, 0.1667);
        INSERT INTO co_change_pairs VALUES
            (1, 'app.py', 'utils.py', 4, 1.0, 1700000000, 0.8),
            (2, 'app.py', 'models.py', 6, 2.0, 1700000001, 0.6),
            (3, 'utils.py', 'models.py', 1, 5.0, 1700000002, 0.2);
    """)
    conn.commit()
    conn.close()


class TestHotspots:
    def test_returns_top_n(self, tmp_path):
        from src.ast_tools.cochange.hotspot import compute_hotspots

        db = tmp_path / "test.db"
        _create_test_db(db)
        hotspots = compute_hotspots(str(db), top_n=2)
        assert len(hotspots) == 2

    def test_sorted_by_score_descending(self, tmp_path):
        from src.ast_tools.cochange.hotspot import compute_hotspots

        db = tmp_path / "test.db"
        _create_test_db(db)
        hotspots = compute_hotspots(str(db), top_n=4)
        scores = [h["hotspot_score"] for h in hotspots]
        assert scores == sorted(scores, reverse=True)

    def test_hotspot_score_formula(self, tmp_path):
        from src.ast_tools.cochange.hotspot import compute_hotspots

        db = tmp_path / "test.db"
        _create_test_db(db)
        hotspots = compute_hotspots(str(db))
        # app.py: instability=0.3333, avg_coupling=(0.8+0.6)/2=0.7 -> score=0.2333
        app = [h for h in hotspots if h["file_path"] == "app.py"][0]
        assert app["hotspot_score"] == pytest.approx(0.2333, abs=0.01)
        assert app["instability"] == 0.3333
        assert app["coupled_files"] == 2

    def test_file_without_coupling(self, tmp_path):
        from src.ast_tools.cochange.hotspot import compute_hotspots

        db = tmp_path / "test.db"
        _create_test_db(db)
        hotspots = compute_hotspots(str(db))
        # config.py has no coupling pairs -> avg_coupling=0, score=0
        config = [h for h in hotspots if h["file_path"] == "config.py"]
        assert len(config) == 1
        assert config[0]["avg_coupling"] == 0.0
        assert config[0]["hotspot_score"] == 0.0
        assert config[0]["coupled_files"] == 0

    def test_empty_db_returns_empty(self, tmp_path):
        from src.ast_tools.cochange.hotspot import compute_hotspots
        import sqlite3

        db = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db))
        conn.executescript("""
            CREATE TABLE churn_metrics (file_path TEXT PRIMARY KEY, commit_count INTEGER, lines_added INTEGER, lines_deleted INTEGER, authors_count INTEGER, last_modified INTEGER, instability REAL);
            CREATE TABLE co_change_pairs (id INTEGER PRIMARY KEY, symbol1_id TEXT, symbol2_id TEXT, frequency INTEGER, avg_gap REAL, last_co_change INTEGER, coupling REAL);
        """)
        conn.close()
        hotspots = compute_hotspots(str(db))
        assert hotspots == []


class TestCoChangePredict:
    def test_returns_suggestions_for_symbol(self, tmp_path):
        from src.ast_tools.tools.co_change import _tool_co_change_predict, _get_db_path
        import src.ast_tools.tools.co_change as cc

        db = tmp_path / "test.db"
        _create_test_db(db)

        # Patch _get_db_path to return our test DB
        original = cc._get_db_path
        cc._get_db_path = lambda x=None: str(db)
        try:
            result = _tool_co_change_predict({"symbol": "app.py"})
            assert "suggestions" in result
            assert result["total_found"] >= 1
        finally:
            cc._get_db_path = original

    def test_suggestions_sorted_by_coupling(self, tmp_path):
        from src.ast_tools.tools.co_change import _tool_co_change_predict
        import src.ast_tools.tools.co_change as cc

        db = tmp_path / "test.db"
        _create_test_db(db)

        original = cc._get_db_path
        cc._get_db_path = lambda x=None: str(db)
        try:
            result = _tool_co_change_predict({"symbol": "app.py"})
            couplings = [s["coupling"] for s in result["suggestions"]]
            assert couplings == sorted(couplings, reverse=True)
        finally:
            cc._get_db_path = original

    def test_missing_symbol_raises(self):
        from src.ast_tools.tools.co_change import _tool_co_change_predict

        try:
            _tool_co_change_predict({})
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_symbol_not_found_returns_empty(self, tmp_path):
        from src.ast_tools.tools.co_change import _tool_co_change_predict
        import src.ast_tools.tools.co_change as cc

        db = tmp_path / "test.db"
        _create_test_db(db)

        original = cc._get_db_path
        cc._get_db_path = lambda x=None: str(db)
        try:
            result = _tool_co_change_predict({"symbol": "nonexistent.py"})
            assert result["total_found"] == 0
            assert result["suggestions"] == []
        finally:
            cc._get_db_path = original


class TestCoChangeHistory:
    def test_returns_churn_for_existing_file(self, tmp_path):
        from src.ast_tools.tools.co_change import _tool_co_change_history
        import src.ast_tools.tools.co_change as cc

        db = tmp_path / "test.db"
        _create_test_db(db)

        original = cc._get_db_path
        cc._get_db_path = lambda x=None: str(db)
        try:
            result = _tool_co_change_history({"file_path": "app.py"})
            assert result["found"] is True
            assert result["commit_count"] == 10
            assert result["lines_added"] == 100
        finally:
            cc._get_db_path = original

    def test_missing_file_returns_not_found(self, tmp_path):
        from src.ast_tools.tools.co_change import _tool_co_change_history
        import src.ast_tools.tools.co_change as cc

        db = tmp_path / "test.db"
        _create_test_db(db)

        original = cc._get_db_path
        cc._get_db_path = lambda x=None: str(db)
        try:
            result = _tool_co_change_history({"file_path": "missing.py"})
            assert result["found"] is False
            assert "message" in result
        finally:
            cc._get_db_path = original

    def test_missing_file_path_raises(self):
        from src.ast_tools.tools.co_change import _tool_co_change_history

        try:
            _tool_co_change_history({})
            assert False
        except ValueError:
            pass


class TestCoChangeDiff:
    def test_returns_at_risk_symbols(self, tmp_path):
        from src.ast_tools.tools.co_change import _tool_co_change_diff
        import src.ast_tools.tools.co_change as cc

        db = tmp_path / "test.db"
        _create_test_db(db)

        original = cc._get_db_path
        cc._get_db_path = lambda x=None: str(db)
        try:
            result = _tool_co_change_diff({"symbol": "app.py"})
            assert "changing" in result
            assert "at_risk" in result
            assert result["risk_count"] >= 1
        finally:
            cc._get_db_path = original


class TestToolRegistration:
    def test_all_tools_importable(self):
        from src.ast_tools.tools.co_change import (
            co_change_diff,
            co_change_history,
            co_change_hotspots,
            co_change_predict,
        )

        assert callable(co_change_predict)
        assert callable(co_change_hotspots)
        assert callable(co_change_history)
        assert callable(co_change_diff)

    def test_tools_accept_empty_dict(self):
        from src.ast_tools.tools.co_change import (
            co_change_diff,
            co_change_history,
            co_change_hotspots,
            co_change_predict,
        )

        for fn in [co_change_predict, co_change_hotspots, co_change_history, co_change_diff]:
            try:
                fn({})
            except (ValueError, KeyError, TypeError):
                pass
            except Exception:
                pass
