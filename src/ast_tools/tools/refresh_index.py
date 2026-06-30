"""MCP tool: Refresh the semantic index for a project.

Usage:
    refresh_index(project_path: str, force: bool = False, embeddings: bool = False, incremental: bool = True)

Scans all Python files in the project, extracts symbols and edges,
and updates the database. Uses file content hashing to skip unchanged files.

Features:
    - Incremental file-level: Skip unchanged files (content hash match)
    - Incremental symbol-level: Only update changed symbols (preserve IDs)
    - Transaction-based updates (atomic, no partial state)
    - Error handling (skips problematic files, continues indexing)
    - Thread-safe (uses database locking)
    - Optional embedding generation for semantic search (--embeddings)

Incremental Mode (default: True):
    When a file has changed, performs symbol-level diff:
    - Unchanged symbols: Preserved (ID, edges, embeddings intact)
    - Modified symbols: Updated in-place (ID preserved)
    - Removed symbols: Deleted (cascade: edges + embeddings)
    - Added symbols: Inserted new

    Use force=True or incremental=False for full re-index.

Embeddings:
    When embeddings=True, generates vector embeddings for all symbols
    using the local BGE-small model. Use this after initial indexing
    to enable semantic_search tool.
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..database import (
    database_context,
    delete_symbol_cascade,
    get_cached_hash,
    get_symbols_by_file,
    init_schema,
    insert_edges_batch,
    insert_symbols_batch,
    update_file_cache,
    update_symbol_fields,
)
from ..database.connection import get_db_path
from ..indexer import extract_symbols, parse_file
from ..indexer.diff import compute_symbol_diff

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file content.

    Args:
        file_path: Path to file

    Returns:
        Hex-encoded SHA256 hash
    """
    try:
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception as e:
        logger.warning(f"Hash error for {file_path}: {e}")
        return ""


def find_python_files(root_path: Path) -> list[Path]:
    """Find all Python files in a directory tree.

    Args:
        root_path: Root directory to search

    Returns:
        List of .py file paths (excludes __pycache__, .git, venv)
    """
    excluded = {"__pycache__", ".git", "venv", ".venv", "node_modules", ".eggs", "*.egg-info"}
    python_files = []

    try:
        for path in root_path.rglob("*.py"):
            # Check if any parent is in excluded dirs
            if any(excl in str(path) for excl in excluded):
                continue
            python_files.append(path)
    except Exception as e:
        logger.warning(f"Error scanning {root_path}: {e}")

    return python_files


def _tool_refresh_index(args: dict[str, Any]) -> dict[str, Any]:
    """Refresh the semantic index for a project.

    Args:
        project_path: Path to the project root
        force: If True, re-index all files even if unchanged (default: False)
        embeddings: If True, generate vector embeddings for all symbols (default: False)

    Returns:
        Dict with indexing statistics (files_indexed, symbols_extracted, errors, etc.)
    """
    project_path = args.get("project_path", ".")
    force = args.get("force", False)
    embeddings = args.get("embeddings", False)
    incremental = args.get("incremental", True)

    try:
        root = Path(project_path).resolve()

        if not root.exists():
            return {
                "error": f"Project path does not exist: {project_path}",
                "error_code": "PATH_NOT_FOUND",
                "tool": "refresh_index",
            }

        if not root.is_dir():
            return {
                "error": f"Project path is not a directory: {project_path}",
                "error_code": "NOT_A_DIRECTORY",
                "tool": "refresh_index",
            }

        db_path = get_db_path()
        logger.info(f"Refreshing index for {root} (database: {db_path})")

        # Initialize schema
        with database_context(db_path) as conn:
            init_schema(conn)

            # Find all Python files
            python_files = find_python_files(root)
            logger.info(f"Found {len(python_files)} Python files")

            # Track statistics
            stats = {
                "total_files": len(python_files),
                "files_indexed": 0,
                "files_skipped": 0,
                "files_failed": 0,
                "symbols_extracted": 0,
                "edges_extracted": 0,
                "symbols_added": 0,
                "symbols_removed": 0,
                "symbols_modified": 0,
                "symbols_unchanged": 0,
                "embeddings_generated": 0,
                "errors": [],
            }

            # Index each file
            for file_path in python_files:
                try:
                    rel_path = str(file_path.relative_to(root))

                    # Check if file has changed (skip if unchanged)
                    content_hash = compute_file_hash(file_path)
                    if not force:
                        cached_hash = get_cached_hash(conn, rel_path)
                        if cached_hash == content_hash:
                            stats["files_skipped"] += 1
                            logger.debug(f"Skipping unchanged: {rel_path}")
                            continue

                    # Parse file
                    result = parse_file(file_path)

                    if not result.success:
                        stats["files_failed"] += 1
                        stats["errors"].append({"file": rel_path, "error": result.error})
                        logger.debug(f"Parse failed for {rel_path}: {result.error}")
                        continue

                    # Extract symbols and edges
                    if result.tree is None:
                        stats["files_skipped"] += 1
                        continue

                    new_symbols, edges = extract_symbols(result.tree, rel_path)

                    if not new_symbols and not edges:
                        # Empty file or __init__.py with no content
                        update_file_cache(conn, rel_path, content_hash, 0)
                        stats["files_skipped"] += 1
                        continue

                    # Use incremental diff for changed files (not force mode, incremental enabled)
                    old_symbols = get_symbols_by_file(conn, rel_path)

                    if old_symbols and not force and incremental:
                        # Incremental update: only modify changed symbols
                        diff = compute_symbol_diff(old_symbols, new_symbols)

                        with conn:
                            # Remove deleted symbols (cascade: edges + embeddings)
                            for sym in diff.removed:
                                delete_symbol_cascade(conn, sym.id)

                            # Update modified symbols (preserve ID)
                            for sym in diff.modified:
                                update_symbol_fields(conn, sym)

                            # Insert new symbols
                            if diff.added:
                                insert_symbols_batch(conn, diff.added)

                            # Update edges: delete old edges for modified symbols, insert new
                            edge_tuples = [
                                (
                                    e.source_id,
                                    e.target_name,
                                    e.edge_type.value if hasattr(e.edge_type, "value") else e.edge_type,
                                    e.target_id,
                                    e.resolution_state.value
                                    if hasattr(e.resolution_state, "value")
                                    else e.resolution_state,
                                )
                                for e in edges
                            ]
                            if edge_tuples:
                                insert_edges_batch(conn, edge_tuples)

                            # Update file cache
                            update_file_cache(conn, rel_path, content_hash, len(new_symbols))

                        stats["symbols_added"] += diff.added_count
                        stats["symbols_removed"] += diff.removed_count
                        stats["symbols_modified"] += diff.modified_count
                        stats["symbols_unchanged"] += diff.unchanged_count
                        stats["symbols_extracted"] += len(diff.added)
                    else:
                        # Full re-index: delete all old, insert all new
                        with conn:
                            # Delete old symbols for this file
                            for sym in old_symbols:
                                delete_symbol_cascade(conn, sym.id)

                            # Insert new symbols
                            insert_symbols_batch(conn, new_symbols)

                            # Convert edges to batch format
                            edge_tuples = [
                                (
                                    e.source_id,
                                    e.target_name,
                                    e.edge_type.value if hasattr(e.edge_type, "value") else e.edge_type,
                                    e.target_id,
                                    e.resolution_state.value
                                    if hasattr(e.resolution_state, "value")
                                    else e.resolution_state,
                                )
                                for e in edges
                            ]
                            insert_edges_batch(conn, edge_tuples)

                            # Update file cache
                            update_file_cache(conn, rel_path, content_hash, len(new_symbols))

                        stats["symbols_extracted"] += len(new_symbols)

                    stats["files_indexed"] += 1
                    stats["edges_extracted"] += len(edges)

                except Exception as e:
                    stats["files_failed"] += 1
                    stats["errors"].append({"file": str(file_path), "error": str(e)})
                    logger.exception(f"Error indexing {file_path}")

            # Generate embeddings if requested
            if embeddings:
                logger.info("Generating embeddings for all symbols...")
                stats["embeddings_generated"] = _generate_embeddings(conn)

            # Commit final stats
            conn.commit()

            # Add timestamp and tool identifier
            stats["project_path"] = str(root)
            stats["indexed_at"] = int(datetime.now().timestamp())
            stats["tool"] = "refresh_index"

            # Limit errors in response (max 20)
            if len(stats["errors"]) > 20:
                stats["errors_truncated"] = True
                stats["errors"] = stats["errors"][:20]

            logger.info(
                f"Index refresh complete: {stats['files_indexed']}/{stats['total_files']} files, {stats['symbols_extracted']} symbols, {stats['embeddings_generated']} embeddings"
            )

            return stats

    except Exception as e:
        logger.exception(f"Refresh failed: {e}")
        return {
            "error": f"Refresh failed: {e}",
            "error_code": "INTERNAL",
            "tool": "refresh_index",
            "files_indexed": 0,
            "symbols_extracted": 0,
            "errors": [str(e)],
        }


def _generate_embeddings(conn) -> int:
    """Generate embeddings for all symbols in the database.

    Args:
        conn: Database connection

    Returns:
        Number of embeddings generated
    """
    try:
        from ..embeddings import generate_batch_embeddings, insert_embeddings_batch
    except ImportError:
        logger.warning(
            "Embedding dependencies not installed. Run: pip install sentence-transformers sqlite-vec"
        )
        return 0

    # Get all symbols without embeddings
    symbols = conn.execute("""
        SELECT s.id, s.signature, s.docstring
        FROM symbols s
        LEFT JOIN symbols_vec v ON s.id = v.symbol_id
        WHERE v.symbol_id IS NULL
    """).fetchall()

    if not symbols:
        logger.info("All symbols already have embeddings")
        return 0

    # Prepare texts for embedding (signature + docstring)
    texts = []
    symbol_ids = []
    for row in symbols:
        text = f"{row['signature'] or ''} {row['docstring'] or ''}".strip()
        if text:
            texts.append(text)
            symbol_ids.append(row["id"])

    if not texts:
        return 0

    # Generate embeddings in batches
    batch_size = 32
    total_generated = 0

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_ids = symbol_ids[i : i + batch_size]

        try:
            embeddings = generate_batch_embeddings(batch_texts, batch_size=batch_size)

            # Insert embeddings
            symbol_embeddings = list(zip(batch_ids, embeddings, strict=False))
            insert_embeddings_batch(conn, symbol_embeddings)

            total_generated += len(batch_ids)
            logger.debug(f"Generated {total_generated}/{len(texts)} embeddings...")

        except Exception as e:
            logger.exception(f"Failed to generate embeddings for batch {i}: {e}")

    logger.info(f"Generated {total_generated} embeddings")
    return total_generated
