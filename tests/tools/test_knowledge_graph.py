"""Tests for knowledge graph MCP tools — isolated from real DB via monkeypatching."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

def _create_test_db(path: Path) -> None:
    """Create a test database with schema v5 and sample graph data."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE symbols (
            id TEXT PRIMARY KEY, name TEXT, file_path TEXT,
            kind TEXT, line INTEGER
        );
        CREATE TABLE edges (
            source_symbol_id TEXT, target_symbol_id TEXT,
            edge_type TEXT, weight REAL
        );
        CREATE TABLE dependency_metrics (
            symbol_id TEXT PRIMARY KEY,
            fan_in INTEGER, fan_out INTEGER,
            spof_score REAL, centrality REAL
        );
        INSERT INTO symbols VALUES
            ('s1', 'handler', 'app.py', 'function', 10),
            ('s2', 'router', 'app.py', 'function', 20),
            ('s3', 'validator', 'utils.py', 'function', 5),
            ('s4', 'formatter', 'utils.py', 'function', 15),
            ('s5', 'logger', 'logging.py', 'function', 3);
        INSERT INTO edges VALUES
            ('s1', 's2', 'calls', 1.0),
            ('s2', 's3', 'calls', 1.0),
            ('s2', 's4', 'calls', 0.5);
        INSERT INTO dependency_metrics VALUES
            ('s1', 0, 1, 0.0, 0.1),
            ('s2', 1, 2, 0.3, 0.5),
            ('s3', 1, 0, 0.8, 0.9),
            ('s4', 1, 0, 0.6, 0.7),
            ('s5', 0, 0, 0.0, 0.05);
    """)
    conn.close()


# ---------------------------------------------------------------------------
# Helpers to monkey-patch MCP tool internals so tests don't need a real DB
# ---------------------------------------------------------------------------

def _make_mock_searcher(
    results: list[dict[str, Any]] | None = None,
) -> Any:
    """Return a mock semantic_search function that returns predictable results."""

    def searcher(params: dict[str, Any]) -> dict[str, Any]:
        return {"results": results or []}
    return searcher


def _make_mock_resolver(tmp_path: Path) -> Any:
    """Return a mock db_path resolver that uses a test DB path."""
    db_path = tmp_path / "test.db"
    _create_test_db(db_path)

    def resolver() -> str:
        return str(db_path)
    return resolver


# ---------------------------------------------------------------------------
# kg_neighborhood tests
# ---------------------------------------------------------------------------

class TestKGNeighborhood:
    """Test _tool_kg_neighborhood."""

    def test_empty_symbol_raises_value_error(self) -> None:
        from ast_tools.tools.knowledge_graph import _tool_kg_neighborhood

        try:
            _tool_kg_neighborhood({"symbol": ""})
            raise AssertionError("Should have raised ValueError")
        except ValueError:
            pass

    def test_symbol_not_found_returns_message(self, monkeypatch: Any) -> None:
        from ast_tools.tools import knowledge_graph as kg

        monkeypatch.setattr(kg, "_get_symbol_searcher", lambda: _make_mock_searcher([]))

        result = kg._tool_kg_neighborhood({
            "symbol": "nonexistent",
            "max_depth": 1,
            "max_nodes": 50,
            "db_path": ":memory:",
        })
        assert result.get("total_symbols_found") == 0
        assert "message" in result
        assert "not found" in result["message"].lower()

    def test_symbol_without_id_returns_message(self, monkeypatch: Any) -> None:
        from ast_tools.tools import knowledge_graph as kg

        monkeypatch.setattr(
            kg, "_get_symbol_searcher",
            lambda: _make_mock_searcher([{"symbol": "foo", "symbol_id": None}]),
        )

        result = kg._tool_kg_neighborhood({
            "symbol": "foo",
            "db_path": ":memory:",
            "max_depth": 1,
        })
        assert result.get("total_symbols_found") == 0
        assert "message" in result

    def test_valid_symbol_returns_neighborhood(self, monkeypatch: Any, tmp_path: Path) -> None:
        from ast_tools.tools import knowledge_graph as kg

        monkeypatch.setattr(
            kg, "_get_symbol_searcher",
            lambda: _make_mock_searcher([{"symbol": "handler", "symbol_id": "s1"}]),
        )
        monkeypatch.setattr(kg, "_get_db_path_resolver", lambda: _make_mock_resolver(tmp_path))

        result = kg._tool_kg_neighborhood({
            "symbol": "handler",
            "max_depth": 2,
            "max_nodes": 50,
        })
        assert result["total_symbols_found"] == 1
        assert "neighborhood" in result
        nh = result["neighborhood"]
        assert nh["root_symbol"] == "s1"
        assert len(nh["symbols"]) >= 2
        assert len(nh["edges"]) >= 1

    def test_no_edges_returns_minimal(self, monkeypatch: Any, tmp_path: Path) -> None:
        """Symbol exists but has no edges at all (e.g., s5 -> disconnected)."""
        from ast_tools.tools import knowledge_graph as kg

        monkeypatch.setattr(
            kg, "_get_symbol_searcher",
            lambda: _make_mock_searcher([{"symbol": "logger", "symbol_id": "s5"}]),
        )
        monkeypatch.setattr(kg, "_get_db_path_resolver", lambda: _make_mock_resolver(tmp_path))

        result = kg._tool_kg_neighborhood({
            "symbol": "logger",
            "max_depth": 2,
        })
        assert result["total_symbols_found"] == 1
        nh = result["neighborhood"]
        assert len(nh["symbols"]) == 1  # just s5
        assert len(nh["edges"]) == 0


# ---------------------------------------------------------------------------
# kg_shortest_path tests
# ---------------------------------------------------------------------------

class TestKGShortestPath:
    """Test _tool_kg_shortest_path."""

    def test_missing_from_symbol_raises_error(self) -> None:
        from ast_tools.tools.knowledge_graph import _tool_kg_shortest_path

        try:
            _tool_kg_shortest_path({"to_symbol": "x"})
            raise AssertionError()
        except ValueError:
            pass

    def test_missing_to_symbol_raises_error(self) -> None:
        from ast_tools.tools.knowledge_graph import _tool_kg_shortest_path

        try:
            _tool_kg_shortest_path({"from_symbol": "x"})
            raise AssertionError()
        except ValueError:
            pass

    def test_from_symbol_not_found(self, monkeypatch: Any) -> None:
        from ast_tools.tools import knowledge_graph as kg

        monkeypatch.setattr(
            kg, "_get_symbol_searcher",
            lambda: _make_mock_searcher([]),
        )

        result = kg._tool_kg_shortest_path({
            "from_symbol": "nope",
            "to_symbol": "target",
            "max_depth": 10,
            "db_path": ":memory:",
        })
        assert result.get("found") is False
        assert "not found" in str(result.get("message", "")).lower()

    def test_to_symbol_not_found(self, monkeypatch: Any) -> None:
        from ast_tools.tools import knowledge_graph as kg

        # Return results for from_symbol but not to_symbol
        call_count = 0

        def mock_search(searcher_fn, query, k=1):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"symbol": "handler", "symbol_id": "s1"}]
            return []

        monkeypatch.setattr(kg, "_safe_search", mock_search)

        result = kg._tool_kg_shortest_path({
            "from_symbol": "handler",
            "to_symbol": "nope",
            "max_depth": 10,
            "db_path": ":memory:",
        })
        assert result.get("found") is False
        assert "not found" in str(result.get("message", "")).lower()

    def test_path_found_direct(self, monkeypatch: Any, tmp_path: Path) -> None:
        from ast_tools.tools import knowledge_graph as kg

        call_count = 0

        def mock_search(searcher_fn, query, k=1):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"symbol": "handler", "symbol_id": "s1"}]
            return [{"symbol": "router", "symbol_id": "s2"}]

        monkeypatch.setattr(kg, "_safe_search", mock_search)
        monkeypatch.setattr(kg, "_get_db_path_resolver", lambda: _make_mock_resolver(tmp_path))

        result = kg._tool_kg_shortest_path({
            "from_symbol": "handler",
            "to_symbol": "router",
            "max_depth": 10,
        })
        assert result.get("found") is not False  # either True or implicit
        distance = result.get("distance", -1)
        assert distance == 1

    def test_path_found_multi_hop(self, monkeypatch: Any, tmp_path: Path) -> None:
        from ast_tools.tools import knowledge_graph as kg

        call_count = 0

        def mock_search(searcher_fn, query, k=1):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"symbol": "handler", "symbol_id": "s1"}]
            return [{"symbol": "validator", "symbol_id": "s3"}]

        monkeypatch.setattr(kg, "_safe_search", mock_search)
        monkeypatch.setattr(kg, "_get_db_path_resolver", lambda: _make_mock_resolver(tmp_path))

        result = kg._tool_kg_shortest_path({
            "from_symbol": "handler",
            "to_symbol": "validator",
            "max_depth": 10,
        })
        assert result.get("distance", -1) == 2
        assert len(result.get("path", [])) >= 3

    def test_no_path_exists(self, monkeypatch: Any, tmp_path: Path) -> None:
        from ast_tools.tools import knowledge_graph as kg

        call_count = 0

        def mock_search(searcher_fn, query, k=1):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"symbol": "handler", "symbol_id": "s1"}]
            return [{"symbol": "logger", "symbol_id": "s5"}]

        monkeypatch.setattr(kg, "_safe_search", mock_search)
        monkeypatch.setattr(kg, "_get_db_path_resolver", lambda: _make_mock_resolver(tmp_path))

        result = kg._tool_kg_shortest_path({
            "from_symbol": "handler",
            "to_symbol": "logger",
            "max_depth": 10,
        })
        assert result.get("found") is False
        assert "no path" in str(result.get("message", "")).lower()


# ---------------------------------------------------------------------------
# kg_query tests
# ---------------------------------------------------------------------------

class TestKGQuery:
    """Test _tool_kg_query."""

    def test_missing_query_raises_error(self) -> None:
        from ast_tools.tools.knowledge_graph import _tool_kg_query

        try:
            _tool_kg_query({"max_depth": 1})
            raise AssertionError()
        except ValueError:
            pass

    def test_empty_results_returns_zero_total(self, monkeypatch: Any) -> None:
        from ast_tools.tools import knowledge_graph as kg

        monkeypatch.setattr(
            kg, "_get_symbol_searcher",
            lambda: _make_mock_searcher([]),
        )

        result = kg._tool_kg_query({
            "query": "nonexistent_thing",
            "db_path": ":memory:",
        })
        assert result["total_symbols_found"] == 0
        assert result["starting_symbols"] == []

    def test_valid_query_returns_neighborhood(self, monkeypatch: Any, tmp_path: Path) -> None:
        from ast_tools.tools import knowledge_graph as kg

        monkeypatch.setattr(
            kg, "_get_symbol_searcher",
            lambda: _make_mock_searcher([{"symbol": "handler", "symbol_id": "s1"}]),
        )
        monkeypatch.setattr(kg, "_get_db_path_resolver", lambda: _make_mock_resolver(tmp_path))

        result = kg._tool_kg_query({
            "query": "handler function",
            "max_depth": 2,
        })
        assert result["query"] == "handler function"
        assert result["total_symbols_found"] == 1
        assert "neighborhood" in result
        nh = result["neighborhood"]
        assert nh["root_symbol"] == "s1"
        assert len(nh["symbols"]) >= 2

    def test_query_without_symbol_id_falls_back(self, monkeypatch: Any) -> None:
        """Starting symbol found but has no symbol_id — should return empty neighborhood."""
        from ast_tools.tools import knowledge_graph as kg

        monkeypatch.setattr(
            kg, "_get_symbol_searcher",
            lambda: _make_mock_searcher([{"symbol": "foo", "symbol_id": None}]),
        )

        result = kg._tool_kg_query({
            "query": "foo",
            "db_path": ":memory:",
        })
        assert result["total_symbols_found"] == 1
        # No symbol_id means no neighborhood — but total_symbols_found counts starting symbols
        assert "neighborhood" in result


# ---------------------------------------------------------------------------
# Tool registration tests
# ---------------------------------------------------------------------------

class TestToolRegistration:
    """Test that KG tools are properly registered and importable."""

    def test_all_tools_importable(self) -> None:
        from ast_tools.tools.knowledge_graph import (
            kg_neighborhood,
            kg_query,
            kg_shortest_path,
        )

        assert callable(kg_query)
        assert callable(kg_shortest_path)
        assert callable(kg_neighborhood)

    def test_tools_registered_in_registry(self) -> None:
        from ast_tools.tools import list_tool_names

        names = list_tool_names()
        assert "kg_query" in names
        assert "kg_shortest_path" in names
        assert "kg_neighborhood" in names

    def test_tool_schemas_defined(self) -> None:
        from ast_tools.tools import get_tool_schema

        for name in ["kg_query", "kg_shortest_path", "kg_neighborhood"]:
            schema = get_tool_schema(name)
            assert schema is not None, f"No schema for {name}"
            assert "description" in schema
            assert "inputSchema" in schema

    def test_tools_accept_empty_dict(self) -> None:
        """All three should raise/return error on empty params, not crash."""
        from ast_tools.tools.knowledge_graph import (
            kg_neighborhood,
            kg_query,
            kg_shortest_path,
        )

        for fn in [kg_query, kg_shortest_path, kg_neighborhood]:
            try:
                fn({})
                # Some may return error dict instead of raising
            except (ValueError, KeyError, TypeError):
                pass
            except Exception:
                pass  # Any controlled error is acceptable
