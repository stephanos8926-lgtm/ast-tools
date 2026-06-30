"""Database package for semantic codebase index.

Submodules:
    connection: Database connection management with retry logic
    schema: Schema definition and migrations
    migrations: Migration framework
    queries: Query functions with batch operations
"""

from .connection import database_context, get_connection, retry_on_locked
from .queries import (
    count_symbols_by_kind,
    delete_symbol_cascade,
    find_symbol_definition,
    get_cached_hash,
    get_index_stats,
    get_symbols_by_file,
    insert_edge,
    insert_edges_batch,
    insert_symbol,
    insert_symbols_batch,
    list_symbols_by_file,
    search_symbols,
    update_file_cache,
    update_symbol_fields,
)
from .schema import get_schema_version, init_schema, needs_migration

__all__ = [
    "count_symbols_by_kind",
    "database_context",
    "delete_symbol_cascade",
    "find_symbol_definition",
    "get_cached_hash",
    # Connection
    "get_connection",
    "get_index_stats",
    "get_schema_version",
    "get_symbols_by_file",
    # Schema
    "init_schema",
    "insert_edge",
    "insert_edges_batch",
    "insert_symbol",
    "insert_symbols_batch",
    "list_symbols_by_file",
    "needs_migration",
    "retry_on_locked",
    # Queries
    "search_symbols",
    "update_file_cache",
    "update_symbol_fields",
]
