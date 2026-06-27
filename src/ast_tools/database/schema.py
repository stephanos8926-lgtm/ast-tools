"""Database schema definition and migrations.

Defines the SQLite schema for the semantic codebase index, including:
- symbols: Core symbol table with FTS5 virtual table
- edges: Relationships between symbols (calls, imports, inherits)
- file_cache: Content-hash tracking for incremental indexing
- schema_version: Version tracking for migrations

All schema changes must be versioned and migratable.
"""

import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime

logger = logging.getLogger(__name__)

# Current schema version - increment when making breaking changes
SCHEMA_VERSION = 5  # Phase 9: Schema Enrichments (callgraph, dependencies, similarity, audit_log)

# Initial schema (v1)
INITIAL_SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

-- Core symbols table
CREATE TABLE IF NOT EXISTS symbols (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('function','class','method','variable','import','constant')),
    file_path TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    signature TEXT,
    docstring TEXT,
    is_public INTEGER DEFAULT 1,
    content_hash TEXT NOT NULL,
    indexed_at INTEGER NOT NULL,
    lang TEXT NOT NULL DEFAULT 'python' CHECK(lang IN ('python','rust','go','typescript','javascript','cpp','c','json','yaml','bash'))
);

-- FTS5 for fast name/search (contentless = halve storage)
CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name, signature, docstring,
    content=''
);

-- Edges (calls, imports, inherits)
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT,  -- Optional, only set when source is a known symbol
    target_name TEXT NOT NULL,
    target_id TEXT,  -- Optional, only set when target is resolved
    edge_type TEXT CHECK(edge_type IN ('calls','imports','inherits','instantiates')),
    resolution_state INTEGER DEFAULT 0,
    UNIQUE(source_id, target_name, edge_type)
);

-- File cache (content-hash tracking for incremental indexing)
CREATE TABLE IF NOT EXISTS file_cache (
    file_path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    embedding_hash TEXT,  -- Hash of docstring+signature for embedding invalidation
    last_indexed INTEGER NOT NULL,
    symbol_count INTEGER DEFAULT 0
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_qualified ON symbols(qualified_name);
CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_file_cache_hash ON file_cache(content_hash);

-- FTS5 sync triggers (auto-update FTS index on symbol changes)
CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, signature, docstring)
    VALUES (NEW.rowid, NEW.name, NEW.signature, NEW.docstring);
END;

CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, signature, docstring)
    VALUES ('delete', OLD.rowid, OLD.name, OLD.signature, OLD.docstring);
END;

CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, signature, docstring)
    VALUES ('delete', OLD.rowid, OLD.name, OLD.signature, OLD.docstring);
    INSERT INTO symbols_fts(rowid, name, signature, docstring)
    VALUES (NEW.rowid, NEW.name, NEW.signature, NEW.docstring);
END;

-- Vector embeddings for semantic search (Phase 2)
CREATE VIRTUAL TABLE IF NOT EXISTS symbols_vec USING vec0(
    symbol_id TEXT PRIMARY KEY,
    embedding FLOAT[384]
);

-- Vector embeddings for semantic search (Phase 2, schema v2)
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema with all tables, indexes, and triggers.

    Args:
        conn: SQLite connection

    Note:
        Idempotent - safe to call multiple times. Uses CREATE IF NOT EXISTS
        for all objects. Does NOT record schema version - use migrate() for that.
    """
    logger.info("Initializing database schema...")
    conn.executescript(INITIAL_SCHEMA)

    # Record schema version if not already present (version 0 -> 1)
    current_version = get_schema_version(conn)
    if current_version == 0:
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (1, int(datetime.now().timestamp())),
        )
        conn.commit()
        logger.info("Schema initialized to version 1")
    else:
        logger.info(f"Schema already at version {current_version}")


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version from database.

    Args:
        conn: SQLite connection

    Returns:
        Schema version number (0 if not initialized)
    """
    try:
        row = conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return row["version"] if row else 0
    except sqlite3.OperationalError:
        # schema_version table doesn't exist yet
        return 0


def needs_migration(conn: sqlite3.Connection) -> bool:
    """Check if database schema needs migration.

    Args:
        conn: SQLite connection

    Returns:
        True if current version < SCHEMA_VERSION
    """
    current = get_schema_version(conn)
    return current < SCHEMA_VERSION


# Migration registry: version -> migration function
MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {}


def register_migration(version: int):
    """Decorator to register a migration function.

    Usage:
        @register_migration(2)
        def migrate_v1_to_v2(conn):
            ...

    Args:
        version: Target schema version for this migration
    """

    def decorator(func: Callable[[sqlite3.Connection], None]):
        MIGRATIONS[version] = func
        return func

    return decorator


def migrate(conn: sqlite3.Connection, target_version: int = SCHEMA_VERSION) -> None:
    """Run all pending migrations to bring database to target version.

    Args:
        conn: SQLite connection
        target_version: Target schema version (default: current SCHEMA_VERSION)

    Raises:
        ValueError: If no migration registered for a required version

    Note:
        Runs migrations inside a transaction. If any migration fails,
        the entire transaction is rolled back.
    """
    current = get_schema_version(conn)

    if current >= target_version:
        logger.info(f"Schema already at version {current}, no migration needed")
        return

    logger.info(f"Migrating schema from version {current} to {target_version}")

    with conn:  # Transaction
        for version in range(current + 1, target_version + 1):
            if version not in MIGRATIONS:
                raise ValueError(f"No migration registered for version {version}")

            logger.info(f"Applying migration to version {version}...")
            MIGRATIONS[version](conn)

            # Update version after successful migration
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, int(datetime.now().timestamp())),
            )

    logger.info(f"Migration complete, schema now at version {get_schema_version(conn)}")


# Example migration stub (implement when adding v2 features)
@register_migration(2)
def migrate_v1_to_v2(conn: sqlite3.Connection):
    """Migration from schema v1 to v2.

    Adds vector embeddings support for semantic search:
    - symbols_vec virtual table (sqlite-vec extension)
    - 384-dimensional embeddings for BGE-small model
    """
    # Create symbols_vec virtual table for vector similarity search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS symbols_vec USING vec0(
            symbol_id TEXT PRIMARY KEY,
            embedding FLOAT[384]
        )
    """)
    logger.info("Migration v1→v2: Added symbols_vec virtual table for vector embeddings")


@register_migration(3)
def migrate_v2_to_v3(conn: sqlite3.Connection):
    """Migration from schema v2 to v3.

    Adds embedding_hash column to file_cache for incremental embedding invalidation.
    """
    # Check if column already exists
    row = conn.execute("""
        SELECT COUNT(*) FROM pragma_table_info('file_cache') WHERE name='embedding_hash'
    """).fetchone()

    if row[0] == 0:
        conn.execute("ALTER TABLE file_cache ADD COLUMN embedding_hash TEXT")
        logger.info("Migration v2→v3: Added embedding_hash column to file_cache")
    else:
        logger.info("Migration v2→v3: embedding_hash column already exists")


@register_migration(4)
def migrate_v3_to_v4(conn: sqlite3.Connection):
    """Migration from schema v3 to v4.

    Adds multi-language support:
    - lang column to symbols table
    - Index on lang for filtering
    """
    # Check if column already exists
    row = conn.execute("""
        SELECT COUNT(*) FROM pragma_table_info('symbols') WHERE name='lang'
    """).fetchone()

    if row[0] == 0:
        conn.execute("""
            ALTER TABLE symbols ADD COLUMN lang TEXT NOT NULL DEFAULT 'python'
        """)
        logger.info("Migration v3→v4: Added lang column to symbols table")
    else:
        logger.info("Migration v3→v4: lang column already exists")

    # Add index on lang for filtering
    conn.execute("CREATE INDEX IF NOT EXISTS idx_symbols_lang ON symbols(lang)")
    logger.info("Migration v3→v4: Added index on symbols.lang")


@register_migration(5)
def migrate_v4_to_v5(conn: sqlite3.Connection):
    """Migration from schema v4 to v5.

    Phase 9 Schema Enrichments:
    - Metadata column to edges with size limit trigger
    - Edge type validation trigger (adds 'implements')
    - dependency_metrics table (fan-in, fan-out, SPOF, instability, centrality)
    - embedding_similarity table (with staleness tracking and model versioning)
    - knn_graph table (for approximate nearest neighbors)
    - audit_log table (security compliance)
    - Composite indexes for query optimization
    - callgraph_edges view (backward compatibility)

    P0 Fixes Applied:
    - UUIDs (TEXT) consistently
    - 384-dim embeddings
    - ON DELETE CASCADE on all FKs
    - Transaction handling
    - ANN for KNN (hnswlib)

    P1 Fixes Applied:
    - Embedding versioning
    - Composite indexes
    - Audit logging
    """
    # Import migration logic from dedicated module
    from ast_tools.database.migrations.migration_009_schema_enrichments import migrate_v4_to_v5

    migrate_v4_to_v5(conn)


def get_migration_sql() -> str:
    """Get the full schema SQL as a string.

    Returns:
        Complete schema SQL for reference or manual inspection
    """
    return INITIAL_SCHEMA
