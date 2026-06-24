"""MCP tool: Refresh the semantic index for a project.

Usage:
    refresh_index(project_path: str, force: bool = False)

Scans all Python files in the project, extracts symbols and edges,
and updates the database. Uses file content hashing to skip unchanged files.

Features:
    - Incremental indexing (only re-indexes changed files)
    - Transaction-based updates (atomic, no partial state)
    - Error handling (skips problematic files, continues indexing)
    - Thread-safe (uses database locking)
"""

from typing import Any
from pathlib import Path
import hashlib
import logging
from datetime import datetime

from ..database import (
    database_context,
    get_cached_hash,
    update_file_cache,
    insert_symbols_batch,
    insert_edges_batch,
    init_schema,
)
from ..database.connection import get_db_path
from ..indexer import parse_file, extract_symbols
from ..types import Edge

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
    excluded = {'__pycache__', '.git', 'venv', '.venv', 'node_modules', '.eggs', '*.egg-info'}
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
    
    Returns:
        Dict with indexing statistics (files_indexed, symbols_extracted, errors, etc.)
    """
    project_path = args.get("project_path", ".")
    force = args.get("force", False)
    
    try:
        root = Path(project_path).resolve()
        
        if not root.exists():
            return {
                "error": f"Project path does not exist: {project_path}",
                "error_code": "PATH_NOT_FOUND",
                "tool": "refresh_index"
            }
        
        if not root.is_dir():
            return {
                "error": f"Project path is not a directory: {project_path}",
                "error_code": "NOT_A_DIRECTORY",
                "tool": "refresh_index"
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
                "errors": []
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
                        stats["errors"].append({
                            "file": rel_path,
                            "error": result.error
                        })
                        logger.debug(f"Parse failed for {rel_path}: {result.error}")
                        continue
                    
                    # Extract symbols and edges
                    if result.tree is None:
                        stats["files_skipped"] += 1
                        continue
                    
                    symbols, edges = extract_symbols(result.tree, rel_path)
                    
                    if not symbols and not edges:
                        # Empty file or __init__.py with no content
                        update_file_cache(conn, rel_path, content_hash, 0)
                        stats["files_skipped"] += 1
                        continue
                    
                    # Insert into database (transaction per file for atomicity)
                    with conn:
                        insert_symbols_batch(conn, symbols)
                        
                        # Convert edges to batch format
                        edge_tuples = [
                            (e.source_id, e.target_name, e.edge_type.value if hasattr(e.edge_type, 'value') else e.edge_type, e.target_id, e.resolution_state.value if hasattr(e.resolution_state, 'value') else e.resolution_state)
                            for e in edges
                        ]
                        insert_edges_batch(conn, edge_tuples)
                        
                        # Update file cache
                        update_file_cache(conn, rel_path, content_hash, len(symbols))
                    
                    stats["files_indexed"] += 1
                    stats["symbols_extracted"] += len(symbols)
                    stats["edges_extracted"] += len(edges)
                    
                except Exception as e:
                    stats["files_failed"] += 1
                    stats["errors"].append({
                        "file": str(file_path),
                        "error": str(e)
                    })
                    logger.exception(f"Error indexing {file_path}")
            
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
            
            logger.info(f"Index refresh complete: {stats['files_indexed']}/{stats['total_files']} files, {stats['symbols_extracted']} symbols")
            
            return stats
    
    except Exception as e:
        logger.exception(f"Refresh failed: {e}")
        return {
            "error": f"Refresh failed: {e}",
            "error_code": "INTERNAL",
            "tool": "refresh_index",
            "files_indexed": 0,
            "symbols_extracted": 0,
            "errors": [str(e)]
        }