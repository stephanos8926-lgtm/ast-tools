"""Tests for the knowledge graph engine."""
import pytest
pytestmark = pytest.mark.unit


from pathlib import Path


def _create_test_db(path: Path) -> None:
    """Create a test database with the v5 schema and sample data."""
    import sqlite3

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


class TestGraphEngine:
    """Test suite for GraphEngine class."""

    def _make_engine(self, tmp_path: Path):
        """Create engine with test data."""
        from ast_tools.kg.graph_engine import GraphEngine

        db_path = tmp_path / "test.db"
        _create_test_db(db_path)
        return GraphEngine(str(db_path)), db_path

    def test_get_neighborhood_depth1(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        nh = e.get_neighborhood("s1", max_depth=1)
        assert nh["root_symbol"] == "s1"
        assert len(nh["symbols"]) == 2  # s1, s2
        assert "s2" in nh["levels"].get(1, [])
        e.close()

    def test_get_neighborhood_depth2(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        nh = e.get_neighborhood("s1", max_depth=2)
        assert len(nh["symbols"]) >= 3  # s1, s2, s3/s4
        assert len(nh["levels"]) >= 2
        e.close()

    def test_get_neighborhood_unknown_symbol(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        nh = e.get_neighborhood("nope", max_depth=2)
        assert nh["root_symbol"] == "nope"
        assert nh["symbols"] == []
        assert nh["edges"] == []
        e.close()

    def test_shortest_path_direct(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        sp = e.shortest_path("s1", "s2")
        assert sp is not None
        assert sp["distance"] == 1
        assert sp["path"] == ["s1", "s2"]
        e.close()

    def test_shortest_path_two_hops(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        sp = e.shortest_path("s1", "s3")
        assert sp is not None
        assert sp["distance"] == 2
        assert sp["path"] == ["s1", "s2", "s3"]
        e.close()

    def test_shortest_path_same_node(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        sp = e.shortest_path("s1", "s1")
        assert sp is not None
        assert sp["distance"] == 0
        assert sp["path"] == ["s1"]
        e.close()

    def test_shortest_path_no_path(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        sp = e.shortest_path("s1", "s5")
        assert sp is None
        e.close()

    def test_centrality_hotspots(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        hs = e.get_centrality_hotspots(3)
        assert len(hs) == 3
        # s3 has highest centrality (0.9)
        assert hs[0]["symbol_id"] == "s3"
        assert hs[0]["name"] == "validator"
        e.close()

    def test_centrality_hotspots_no_limit(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        hs = e.get_centrality_hotspots(100)
        assert len(hs) == 5  # all 5 symbols
        e.close()

    def test_centrality_hotspots_empty_table(self, tmp_path: Path) -> None:
        """With no dependency_metrics data, should return empty."""
        import sqlite3
        from ast_tools.kg.graph_engine import GraphEngine

        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE symbols (id TEXT PRIMARY KEY, name TEXT, file_path TEXT, kind TEXT, line INTEGER);
            CREATE TABLE edges (source_symbol_id TEXT, target_symbol_id TEXT, edge_type TEXT, weight REAL);
            CREATE TABLE dependency_metrics (symbol_id TEXT PRIMARY KEY, fan_in INTEGER, fan_out INTEGER, spof_score REAL, centrality REAL);
        """)
        conn.close()
        e = GraphEngine(str(db_path))
        hs = e.get_centrality_hotspots(10)
        assert hs == []
        e.close()

    def test_clusters(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        cl = e.get_clusters(min_size=2)
        assert len(cl) >= 1
        # s1/s2/s3/s4 should be in the same component
        first = cl[0]
        assert first["size"] >= 3
        e.close()

    def test_clusters_no_edges(self, tmp_path: Path) -> None:
        import sqlite3
        from ast_tools.kg.graph_engine import GraphEngine

        db_path = tmp_path / "no_edges.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE symbols (id TEXT PRIMARY KEY, name TEXT, file_path TEXT, kind TEXT, line INTEGER);
            CREATE TABLE edges (source_symbol_id TEXT, target_symbol_id TEXT, edge_type TEXT, weight REAL);
            CREATE TABLE dependency_metrics (symbol_id TEXT PRIMARY KEY, fan_in INTEGER, fan_out INTEGER, spof_score REAL, centrality REAL);
        """)
        conn.close()
        e = GraphEngine(str(db_path))
        cl = e.get_clusters()
        assert cl == []
        e.close()

    def test_bfs(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        bfs = e.bfs("s1", depth_limit=2)
        assert 0 in bfs["levels"]
        assert 1 in bfs["levels"]
        assert len(bfs["levels"]) >= 2
        e.close()

    def test_bfs_depth_limit(self, tmp_path: Path) -> None:
        e, _ = self._make_engine(tmp_path)
        bfs = e.bfs("s1", depth_limit=1)
        assert 0 in bfs["levels"]
        assert 1 in bfs["levels"]
        assert 2 not in bfs["levels"]
        e.close()

    def test_round_trip_nonexistent_db(self, tmp_path: Path) -> None:
        """Should handle missing database by creating file (SQLite behavior)."""
        from ast_tools.kg.graph_engine import GraphEngine

        db_path = tmp_path / "nonexistent.db"
        e = GraphEngine(str(db_path))  # SQLite creates the file
        assert e is not None
        e.close()
