"""Database package for semantic codebase index.

Submodules:
    connection: Database connection management with retry logic
    schema: Schema definition and migrations
    migrations: Migration framework
    queries: Query functions with batch operations
"""

from .connection import get_connection, database_context, retry_on_locked
from .schema import init_schema, get_schema_version, needs_migration
from .queries import (
    search_symbols,
    find_symbol_definition,
    list_symbols_by_file,
    get_cached_hash,
    update_file_cache,
    insert_symbol,
    insert_symbols_batch,
    insert_edge,
    insert_edges_batch,
    get_index_stats,
    count_symbols_by_kind,
)

__all__ = [
    # Connection
    "get_connection",
    "database_context",
    "retry_on_locked",
    # Schema
    "init_schema",
    "get_schema_version",
    "needs_migration",
    # Queries
    "search_symbols",
    "find_symbol_definition",
    "list_symbols_by_file",
    "get_cached_hash",
    "update_file_cache",
    "insert_symbol",
    "insert_symbols_batch",
    "insert_edge",
    "insert_edges_batch",
    "get_index_stats",
    "count_symbols_by_kind",
]