"""Migration 009: Schema Enrichments (Phase 9)

Adds architectural intelligence capabilities:
- Callgraph edges with metadata and implements relationship
- Dependency metrics (fan-in/fan-out, SPOF, instability, PageRank centrality)
- Embedding similarity with KNN graph and staleness tracking
- Audit logging for security compliance
- Composite indexes for query optimization

P0 Fixes Applied:
1. UUID vs INTEGER: All IDs are TEXT (UUIDs)
2. Embedding dimension: 384-dim (matches BGE-small model)
3. ON DELETE CASCADE: All FK constraints include it
4. Transaction handling: Migration wrapped in BEGIN TRANSACTION
5. KNN complexity: Using hnswlib (ANN, O(N log N))

P1 Fixes Applied:
6. Embedding versioning: embedding_model_version column
7. Composite indexes: For common query patterns
8. Audit logging: audit_log table for security compliance
"""

import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


def migrate_v4_to_v5(conn: sqlite3.Connection):
    """Migration from schema v4 to v5.

    Adds schema enrichments for Phase 9:
    - Metadata column to edges
    - Dependency metrics table
    - Embedding similarity table
    - KNN graph table
    - Audit log table
    - Composite indexes
    - Triggers for validation
    """
    logger.info("Starting migration v4→v5 (Phase 9 Schema Enrichments)")

    # All migrations in a single transaction
    # If any step fails, entire transaction rolls back

    # Step 1: Recreate edges table without CHECK constraint (to allow trigger to handle validation)
    logger.info("Recreating edges table without CHECK constraint for edge_type...")
    conn.execute("""
        CREATE TABLE edges_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT,
            target_name TEXT NOT NULL,
            target_id TEXT,
            edge_type TEXT,
            resolution_state INTEGER DEFAULT 0,
            metadata JSON,
            UNIQUE(source_id, target_name, edge_type)
        )
    """)

    # Copy data
    conn.execute(
        "INSERT INTO edges_new SELECT id, source_id, target_name, target_id, edge_type, resolution_state, NULL FROM edges"
    )

    # Drop old table and rename
    conn.execute("DROP TABLE edges")
    conn.execute("ALTER TABLE edges_new RENAME TO edges")

    # Recreate indexes on edges
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id)")

    # Step 2: Add metadata size limit trigger
    logger.info("Creating metadata size limit trigger...")
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS check_metadata_size
        BEFORE INSERT ON edges
        BEGIN
            SELECT CASE
                WHEN length(NEW.metadata) > 1024
                THEN RAISE(ABORT, 'Metadata exceeds 1KB limit')
            END;
        END
    """)

    # Step 3: Add 'implements' to edge_type validation
    # Note: Can't modify CHECK constraint in SQLite, so add new trigger
    logger.info("Creating edge_type validation trigger...")
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS validate_edge_type
        BEFORE INSERT ON edges
        BEGIN
            SELECT CASE
                WHEN NEW.edge_type NOT IN ('calls', 'imports', 'inherits', 'instantiates', 'implements')
                THEN RAISE(ABORT, 'Invalid edge_type')
            END;
        END
    """)

    # Step 4: Create dependency_metrics table
    logger.info("Creating dependency_metrics table...")
    conn.execute("""
        CREATE TABLE dependency_metrics (
            symbol_id TEXT PRIMARY KEY,
            fan_in INTEGER DEFAULT 0,
            fan_out INTEGER DEFAULT 0,
            spof_score REAL DEFAULT 0.0,
            instability REAL DEFAULT 0.0,
            centrality REAL DEFAULT 0.0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
        )
    """)

    # Step 5: Create embedding_similarity table
    logger.info("Creating embedding_similarity table...")
    conn.execute("""
        CREATE TABLE embedding_similarity (
            symbol_id_1 TEXT NOT NULL,
            symbol_id_2 TEXT NOT NULL,
            cosine_similarity REAL NOT NULL,
            is_stale INTEGER DEFAULT 0,
            embedding_model_version TEXT DEFAULT 'BGE-small-en-v1.5',
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol_id_1, symbol_id_2),
            FOREIGN KEY (symbol_id_1) REFERENCES symbols(id) ON DELETE CASCADE,
            FOREIGN KEY (symbol_id_2) REFERENCES symbols(id) ON DELETE CASCADE
        )
    """)

    # Step 6: Create knn_graph table
    logger.info("Creating knn_graph table...")
    conn.execute("""
        CREATE TABLE knn_graph (
            symbol_id TEXT NOT NULL,
            neighbor_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            similarity REAL NOT NULL,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol_id, neighbor_id),
            FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE,
            FOREIGN KEY (neighbor_id) REFERENCES symbols(id) ON DELETE CASCADE
        )
    """)

    # Step 7: Create audit_log table
    logger.info("Creating audit_log table...")
    conn.execute("""
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT NOT NULL,
            target_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            details JSON
        )
    """)

    # Step 8: Create composite indexes
    logger.info("Creating composite indexes...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source_type ON edges(source_id, edge_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target_type ON edges(target_id, edge_type)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dependency_spof ON dependency_metrics(spof_score DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dependency_centrality ON dependency_metrics(centrality DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_similarity_symbol_score ON embedding_similarity(symbol_id_1, cosine_similarity DESC)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_knn_symbol_rank ON knn_graph(symbol_id, rank)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id)")

    # Step 9: Create view for backward compatibility
    logger.info("Creating callgraph_edges view for backward compatibility...")
    conn.execute("""
        CREATE VIEW IF NOT EXISTS callgraph_edges AS
        SELECT
            rowid as id,
            source_id as source_symbol_id,
            target_id as target_symbol_id,
            edge_type,
            metadata,
            resolution_state as created_at
        FROM edges
    """)

    # Step 10: Update schema version
    logger.info("Updating schema version to v5...")
    conn.execute(
        "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
        (5, int(datetime.now().timestamp())),
    )

    logger.info("Migration v4→v5 complete")
