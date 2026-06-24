"""Tests for migration 009 rollback procedure.

Tests:
- Rollback successfully removes new tables
- Rollback preserves original data
- Rollback restores schema version to v4
"""

import pytest
import sqlite3
import tempfile
import os

from ast_tools.database.schema import migrate, get_schema_version, init_schema
from ast_tools.database.migrations.migration_009_schema_enrichments import migrate_v4_to_v5


@pytest.fixture
def migrated_db():
    """Create a database migrated to v5 with test data."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_path)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Initialize and migrate to v5
    init_schema(conn)
    migrate(conn, target_version=4)
    migrate(conn, target_version=5)
    
    # Insert test data
    conn.execute(
        "INSERT INTO symbols (id, name, qualified_name, kind, file_path, content_hash, indexed_at, lang) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("test-symbol", "test_func", "test.func", "function", "/test.py", "hash123", 123456, "python")
    )
    
    conn.execute(
        "INSERT INTO dependency_metrics (symbol_id, fan_in, fan_out, spof_score) VALUES (?, ?, ?, ?)",
        ("test-symbol", 5, 10, 0.8)
    )
    
    conn.execute(
        "INSERT INTO edges (source_id, target_name, edge_type, metadata) VALUES (?, ?, ?, ?)",
        ("test-symbol", "other_func", "calls", '{"callsite": "line 10"}')
    )
    
    conn.commit()
    
    yield conn
    
    conn.close()
    os.unlink(db_path)


def test_rollback_removes_new_tables(migrated_db):
    """Test that rollback removes Phase 9 tables."""
    # Verify tables exist before rollback
    tables_before = migrated_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names_before = [t[0] for t in tables_before]
    
    assert 'dependency_metrics' in table_names_before
    assert 'embedding_similarity' in table_names_before
    assert 'knn_graph' in table_names_before
    assert 'audit_log' in table_names_before
    
    # Perform rollback (manual for testing)
    rollback_v5_to_v4(migrated_db)
    
    # Verify tables removed after rollback
    tables_after = migrated_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names_after = [t[0] for t in tables_after]
    
    assert 'dependency_metrics' not in table_names_after
    assert 'embedding_similarity' not in table_names_after
    assert 'knn_graph' not in table_names_after
    assert 'audit_log' not in table_names_after


def test_rollback_removes_triggers(migrated_db):
    """Test that rollback removes Phase 9 triggers."""
    # Verify triggers exist before rollback
    triggers_before = migrated_db.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'"
    ).fetchall()
    trigger_names_before = [t[0] for t in triggers_before]
    
    assert 'check_metadata_size' in trigger_names_before
    assert 'validate_edge_type' in trigger_names_before
    
    # Perform rollback
    rollback_v5_to_v4(migrated_db)
    
    # Verify triggers removed
    triggers_after = migrated_db.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger'"
    ).fetchall()
    trigger_names_after = [t[0] for t in triggers_after]
    
    assert 'check_metadata_size' not in trigger_names_after
    assert 'validate_edge_type' not in trigger_names_after


def test_rollback_removes_indexes(migrated_db):
    """Test that rollback removes Phase 9 indexes."""
    # Verify indexes exist before rollback
    indexes_before = migrated_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    ).fetchall()
    index_names_before = [i[0] for i in indexes_before]
    
    # Phase 9 indexes
    phase9_indexes = [
        'idx_edges_source_type',
        'idx_edges_target_type',
        'idx_dependency_spof',
        'idx_dependency_centrality',
        'idx_similarity_symbol_score',
        'idx_knn_symbol_rank',
        'idx_audit_log_timestamp',
        'idx_audit_log_user',
    ]
    
    for idx in phase9_indexes:
        assert idx in index_names_before, f"Missing index before rollback: {idx}"
    
    # Perform rollback
    rollback_v5_to_v4(migrated_db)
    
    # Verify Phase 9 indexes removed
    indexes_after = migrated_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    ).fetchall()
    index_names_after = [i[0] for i in indexes_after]
    
    for idx in phase9_indexes:
        assert idx not in index_names_after, f"Index still exists after rollback: {idx}"


def test_rollback_removes_view(migrated_db):
    """Test that rollback removes callgraph_edges view."""
    # Verify view exists before rollback
    views_before = migrated_db.execute(
        "SELECT name FROM sqlite_master WHERE type='view' AND name='callgraph_edges'"
    ).fetchall()
    assert len(views_before) == 1
    
    # Perform rollback
    rollback_v5_to_v4(migrated_db)
    
    # Verify view removed
    views_after = migrated_db.execute(
        "SELECT name FROM sqlite_master WHERE type='view' AND name='callgraph_edges'"
    ).fetchall()
    assert len(views_after) == 0


def test_rollback_restores_schema_version(migrated_db):
    """Test that rollback restores schema version to v4."""
    # Verify at v5 before rollback
    assert get_schema_version(migrated_db) == 5
    
    # Perform rollback
    rollback_v5_to_v4(migrated_db)
    
    # Verify at v4 after rollback
    assert get_schema_version(migrated_db) == 4


def test_rollback_preserves_original_data(migrated_db):
    """Test that rollback preserves symbols and edges data."""
    # Count records before rollback
    symbols_before = migrated_db.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    edges_before = migrated_db.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    
    assert symbols_before == 1
    assert edges_before >= 1
    
    # Perform rollback
    rollback_v5_to_v4(migrated_db)
    
    # Count records after rollback
    symbols_after = migrated_db.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    edges_after = migrated_db.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    
    # Original data should be preserved
    assert symbols_after == symbols_before
    assert edges_after == edges_before


def test_rollback_removes_dependency_metrics_data(migrated_db):
    """Test that rollback removes dependency_metrics data (cascaded deletion not applicable)."""
    # Verify metrics exist before rollback
    metrics_before = migrated_db.execute(
        "SELECT COUNT(*) FROM dependency_metrics WHERE symbol_id = 'test-symbol'"
    ).fetchone()[0]
    assert metrics_before == 1
    
    # Perform rollback
    rollback_v5_to_v4(migrated_db)
    
    # Table should not exist, so query should fail
    with pytest.raises(sqlite3.OperationalError, match="no such table: dependency_metrics"):
        migrated_db.execute("SELECT COUNT(*) FROM dependency_metrics").fetchone()


def rollback_v5_to_v4(conn):
    """Manual rollback procedure for testing.
    
    In production, this would be in a separate rollback script.
    """
    with conn:  # Transaction
        # Drop tables (reverse dependency order)
        conn.execute("DROP TABLE IF EXISTS audit_log")
        conn.execute("DROP TABLE IF EXISTS knn_graph")
        conn.execute("DROP TABLE IF EXISTS embedding_similarity")
        conn.execute("DROP TABLE IF EXISTS dependency_metrics")
        
        # Drop triggers
        conn.execute("DROP TRIGGER IF EXISTS check_metadata_size")
        conn.execute("DROP TRIGGER IF EXISTS validate_edge_type")
        
        # Drop view
        conn.execute("DROP VIEW IF EXISTS callgraph_edges")
        
        # Drop Phase 9 indexes
        conn.execute("DROP INDEX IF EXISTS idx_edges_source_type")
        conn.execute("DROP INDEX IF EXISTS idx_edges_target_type")
        conn.execute("DROP INDEX IF EXISTS idx_dependency_spof")
        conn.execute("DROP INDEX IF EXISTS idx_dependency_centrality")
        conn.execute("DROP INDEX IF EXISTS idx_similarity_symbol_score")
        conn.execute("DROP INDEX IF EXISTS idx_knn_symbol_rank")
        conn.execute("DROP INDEX IF EXISTS idx_audit_log_timestamp")
        conn.execute("DROP INDEX IF EXISTS idx_audit_log_user")
        
        # Revert schema version
        conn.execute("UPDATE schema_version SET version = 4")
    
    # Note: Can't drop metadata column from edges (SQLite limitation)
    # It will remain as a nullable, unused column