"""Database schema definition and migrations.

Defines the SQLite schema for the semantic codebase index, including:
- symbols: Core symbol table with FTS5 virtual table
- edges: Relationships between symbols (calls, imports, inherits)
- file_cache: Content-hash tracking for incremental indexing
- schema_version: Version tracking for migrations

All schema changes must be versioned and migratable.
"""

import sqlite3
from pathlib import Path
from typing import List, Tuple, Callable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Current schema version - increment when making breaking changes
SCHEMA_VERSION = 1

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
    indexed_at INTEGER NOT NULL
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
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema with all tables, indexes, and triggers.
    
    Args:
        conn: SQLite connection
    
    Note:
        Idempotent - safe to call multiple times. Uses CREATE IF NOT EXISTS
        for all objects. Records schema version after successful init.
    """
    logger.info("Initializing database schema...")
    conn.executescript(INITIAL_SCHEMA)
    
    # Record schema version if not already present
    current_version = get_schema_version(conn)
    if current_version < SCHEMA_VERSION:
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, int(datetime.now().timestamp()))
        )
        conn.commit()
        logger.info(f"Schema initialized to version {SCHEMA_VERSION}")
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
        return row['version'] if row else 0
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
                (version, int(datetime.now().timestamp()))
            )
    
    logger.info(f"Migration complete, schema now at version {get_schema_version(conn)}")


# Example migration stub (implement when adding v2 features)
@register_migration(2)
def migrate_v1_to_v2(conn: sqlite3.Connection):
    """Migration from schema v1 to v2.
    
    Reserved for future schema changes. Example changes might include:
    - Adding new symbol kinds (decorator, context_manager, etc.)
    - Adding new edge types (assigns, raises, yields)
    - Adding embedding columns for vector search
    - Adding performance indexes
    """
    # Example: Add new symbol kind to CHECK constraint
    # conn.execute("ALTER TABLE symbols ADD COLUMN decorator_name TEXT")
    logger.info("Migration v1→v2: No changes yet (stub)")
    pass


def get_migration_sql() -> str:
    """Get the full schema SQL as a string.
    
    Returns:
        Complete schema SQL for reference or manual inspection
    """
    return INITIAL_SCHEMA