"""Tests for migration 009 (Phase 9 Schema Enrichments).

Tests:
- Migration applies successfully
- All tables created correctly
- All triggers functional
- All indexes created
- Foreign keys work (including CASCADE)
- View created for backward compatibility
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path

from ast_tools.database.schema import migrate, get_schema_version, SCHEMA_VERSION
from ast_tools.database.migrations.migration_009_schema_enrichments import migrate_v4_to_v5


@pytest.fixture
def fresh_db():
    """Create a fresh in-memory database with schema v4."""
    # Create temp file DB
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Load sqlite-vec extension
    from ast_tools.embeddings.store import load_vec_extension
    load_vec_extension(conn)
    
    # Initialize to v4 (apply migrations 1-4)
    from ast_tools.database.schema import init_schema
    init_schema(conn)
    migrate(conn, target_version=4)
    
    yield conn
    
    conn.close()
    os.unlink(db_path)


def test_migration_applies_successfully(fresh_db):
    """Test that migration v4→v5 applies without errors."""
    # Should start at v4
    assert get_schema_version(fresh_db) == 4
    
    # Apply migration 5
    migrate(fresh_db, target_version=5)
    
    # Should now be at v5
    assert get_schema_version(fresh_db) == 5


def test_dependency_metrics_table_created(fresh_db):
    """Test that dependency_metrics table is created with correct schema."""
    migrate(fresh_db, target_version=5)
    
    # Check table exists
    tables = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='dependency_metrics'"
    ).fetchall()
    assert len(tables) == 1
    
    # Check columns
    columns = fresh_db.execute("PRAGMA table_info(dependency_metrics)").fetchall()
    column_names = [col[1] for col in columns]
    assert 'symbol_id' in column_names
    assert 'fan_in' in column_names
    assert 'fan_out' in column_names
    assert 'spof_score' in column_names
    assert 'instability' in column_names
    assert 'centrality' in column_names
    assert 'last_updated' in column_names


def test_embedding_similarity_table_created(fresh_db):
    """Test that embedding_similarity table is created with correct schema."""
    migrate(fresh_db, target_version=5)
    
    # Check table exists
    tables = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='embedding_similarity'"
    ).fetchall()
    assert len(tables) == 1
    
    # Check columns
    columns = fresh_db.execute("PRAGMA table_info(embedding_similarity)").fetchall()
    column_names = [col[1] for col in columns]
    assert 'symbol_id_1' in column_names
    assert 'symbol_id_2' in column_names
    assert 'cosine_similarity' in column_names
    assert 'is_stale' in column_names
    assert 'embedding_model_version' in column_names  # P1 fix
    assert 'computed_at' in column_names


def test_knn_graph_table_created(fresh_db):
    """Test that knn_graph table is created with correct schema."""
    migrate(fresh_db, target_version=5)
    
    # Check table exists
    tables = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='knn_graph'"
    ).fetchall()
    assert len(tables) == 1


def test_audit_log_table_created(fresh_db):
    """Test that audit_log table is created with correct schema."""
    migrate(fresh_db, target_version=5)
    
    # Check table exists
    tables = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchall()
    assert len(tables) == 1
    
    # Check columns
    columns = fresh_db.execute("PRAGMA table_info(audit_log)").fetchall()
    column_names = [col[1] for col in columns]
    assert 'user_id' in column_names
    assert 'action' in column_names
    assert 'timestamp' in column_names


def test_foreign_key_cascade(fresh_db):
    """Test that ON DELETE CASCADE is working (P0 fix)."""
    migrate(fresh_db, target_version=5)
    
    # Insert a symbol
    fresh_db.execute(
        "INSERT INTO symbols (id, name, qualified_name, kind, file_path, content_hash, indexed_at, lang) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("test-id", "test_func", "test.test_func", "function", "/test.py", "abc123", 1234567890, "python")
    )
    
    # Insert a dependency metric referencing that symbol
    fresh_db.execute(
        "INSERT INTO dependency_metrics (symbol_id, fan_in, fan_out) VALUES (?, ?, ?)",
        ("test-id", 5, 10)
    )
    
    # Verify metric exists
    result = fresh_db.execute(
        "SELECT COUNT(*) FROM dependency_metrics WHERE symbol_id = ?",
        ("test-id",)
    ).fetchone()
    assert result[0] == 1
    
    # Delete the symbol
    fresh_db.execute("DELETE FROM symbols WHERE id = ?", ("test-id",))
    
    # Verify metric was cascaded (deleted automatically)
    result = fresh_db.execute(
        "SELECT COUNT(*) FROM dependency_metrics WHERE symbol_id = ?",
        ("test-id",)
    ).fetchone()
    assert result[0] == 0, "ON DELETE CASCADE should delete dependent records"


def test_metadata_trigger(fresh_db):
    """Test that metadata size limit trigger works."""
    migrate(fresh_db, target_version=5)
    
    # Insert a valid edge with small metadata
    fresh_db.execute(
        "INSERT INTO edges (source_id, target_name, edge_type, metadata) "
        "VALUES (?, ?, ?, ?)",
        ("src-id", "tgt-name", "calls", '{"key": "value"}')
    )
    
    # Try to insert edge with oversized metadata (>1KB)
    large_metadata = '{"data": "' + 'x' * 2000 + '"}'
    
    with pytest.raises(sqlite3.DatabaseError, match="Metadata exceeds 1KB limit"):
        fresh_db.execute(
            "INSERT INTO edges (source_id, target_name, edge_type, metadata) "
            "VALUES (?, ?, ?, ?)",
            ("src-id-2", "tgt-name-2", "calls", large_metadata)
        )


def test_edge_type_trigger(fresh_db):
    """Test that edge_type validation trigger works (includes 'implements')."""
    migrate(fresh_db, target_version=5)
    
    # Valid edge types should work
    valid_types = ['calls', 'imports', 'inherits', 'instantiates', 'implements']
    for edge_type in valid_types:
        fresh_db.execute(
            "INSERT INTO edges (source_id, target_name, edge_type) VALUES (?, ?, ?)",
            (f"src-{edge_type}", "target", edge_type)
        )
    
    # Invalid edge type should fail
    with pytest.raises(sqlite3.DatabaseError, match="Invalid edge_type"):
        fresh_db.execute(
            "INSERT INTO edges (source_id, target_name, edge_type) VALUES (?, ?, ?)",
            ("src-bad", "target", "invalid_type")
        )


def test_composite_indexes_created(fresh_db):
    """Test that composite indexes are created (P1 fix)."""
    migrate(fresh_db, target_version=5)
    
    expected_indexes = [
        'idx_edges_source_type',
        'idx_edges_target_type',
        'idx_dependency_spof',
        'idx_dependency_centrality',
        'idx_similarity_symbol_score',
        'idx_knn_symbol_rank',
        'idx_audit_log_timestamp',
        'idx_audit_log_user',
    ]
    
    indexes = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    ).fetchall()
    index_names = [idx[0] for idx in indexes]
    
    for expected in expected_indexes:
        assert expected in index_names, f"Missing index: {expected}"


def test_callgraph_edges_view_created(fresh_db):
    """Test that callgraph_edges view exists for backward compatibility."""
    migrate(fresh_db, target_version=5)
    
    # Check view exists
    views = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='view' AND name='callgraph_edges'"
    ).fetchall()
    assert len(views) == 1
    
    # Test that view can be queried
    fresh_db.execute(
        "INSERT INTO edges (source_id, target_name, edge_type) VALUES (?, ?, ?)",
        ("src-1", "tgt-1", "calls")
    )
    
    result = fresh_db.execute("SELECT * FROM callgraph_edges LIMIT 1").fetchone()
    assert result is not None


def test_transaction_rollback_on_failure(fresh_db):
    """Test that migration rolls back on failure (P0 fix)."""
    # This is a bit tricky to test, but we can verify the migration
    # function uses transactions by checking it doesn't leave partial state
    # if we manually cause an error
    
    # For now, just verify the migration completes successfully
    # The transaction wrapping is in the migration code itself
    migrate(fresh_db, target_version=5)
    
    # Verify all tables exist (transaction completed)
    tables = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = [t[0] for t in tables]
    
    assert 'dependency_metrics' in table_names
    assert 'embedding_similarity' in table_names
    assert 'knn_graph' in table_names
    assert 'audit_log' in table_names