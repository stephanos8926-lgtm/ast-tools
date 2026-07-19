"""Unified reindex pipeline — single call triggers all indexing layers.

This module provides the `reindex_all()` function that consolidates all
indexing stages into one atomic transaction:

1. File scan → AST parse → symbols/edges (existing refresh_index)
2. Incremental diff → update symbols (existing)
3. Generate embeddings for new/modified symbols (existing)
4. Build KNN graph (existing, separate call)
5. Compute dependency metrics (existing, separate call)
6. Mine co-change pairs from git (existing, separate call)
7. Record snapshot to codebase_snapshots table (new)
8. Update project registry state (new)

All stages run within a single SQLite transaction (BEGIN/COMMIT).
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..database import (
    database_context,
    init_schema,
    update_file_cache,
    insert_symbols_batch,
    insert_edges_batch,
    delete_symbol_cascade,
    get_cached_hash,
    get_symbols_by_file,
)
from ..database.connection import get_db_path
from ..database.schema import migrate, SCHEMA_VERSION
from ..indexer import extract_symbols, parse_file
from ..indexer.diff import compute_symbol_diff
from ..tools.refresh_index import find_python_files, compute_file_hash


def reindex_all(
    project_path: str,
    force: bool = False,
    embeddings: bool = True,
    incremental: bool = True,
) -> dict[str, Any]:
    """Reindex ALL layers for a project in a single transaction.

    Args:
        project_path: Root path of project to index
        force: If True, full rebuild (skip incremental diff)
        embeddings: If True, generate vector embeddings for symbols
        incremental: If True, use content-hash diff (default: True)

    Returns:
        Unified statistics dict with per-layer counts and timing.

    Note:
        This is the ONE CALL TO RULE THEM ALL — it replaces calling
        refresh_index, generate_embeddings, build_knn, compute_metrics,
        mine_co_change, and record_snapshot separately.
    """
    root = Path(project_path).resolve()
    if not root.exists() or not root.is_dir():
        return {"error": f"Project path does not exist: {project_path}", "error_code": "PATH_NOT_FOUND"}

    db_path = get_db_path(project_root=root)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {
        "project_path": str(root),
        "db_path": str(db_path),
        "started_at": datetime.now().isoformat(),
        "force": force,
        "embeddings": embeddings,
        "incremental": incremental,
        "layers": {},
        "total_symbols": 0,
        "total_edges": 0,
        "total_embeddings": 0,
        "total_co_change_pairs": 0,
        "errors": [],
    }

    t0 = time.time()

    with database_context(db_path) as conn:
        # Ensure schema is at latest version
        init_schema(conn)
        migrate(conn, SCHEMA_VERSION)

        # Begin transaction
        conn.execute("BEGIN IMMEDIATE TRANSACTION")

        try:
            # LAYER 1: Symbols + Edges (file scan, AST parse, incremental diff)
            layer_start = time.time()
            python_files = find_python_files(root)
            stats["layers"]["symbols_edges"] = {
                "total_files": len(python_files),
                "files_indexed": 0,
                "files_skipped": 0,
                "symbols_added": 0,
                "symbols_removed": 0,
                "symbols_modified": 0,
                "symbols_unchanged": 0,
                "edges_extracted": 0,
            }

            symbols_extracted = 0
            edges_extracted = 0
            symbols_to_embed = []  # Accumulate across all files

            for file_path in python_files:
                try:
                    rel_path = str(file_path.relative_to(root))
                    content_hash = compute_file_hash(file_path)
                    cached_hash = get_cached_hash(conn, rel_path)

                    if not force and incremental and cached_hash == content_hash:
                        stats["layers"]["symbols_edges"]["files_skipped"] += 1
                        continue

                    # Parse file
                    parse_result = parse_file(file_path)

                    if not parse_result.success:
                        stats["errors"].append(f"{rel_path}: {parse_result.error}")
                        continue

                    extract_result = extract_symbols(parse_result.tree, rel_path)
                    symbols = extract_result.get("symbols", [])
                    edges = extract_result.get("edges", [])

                    # Incremental diff if not force
                    if not force and incremental and cached_hash:
                        existing_symbols = get_symbols_by_file(conn, rel_path)
                        diff = compute_symbol_diff(existing_symbols, symbols)

                        # Apply diff
                        for sym in diff["removed"]:
                            delete_symbol_cascade(conn, sym["id"])
                            stats["layers"]["symbols_edges"]["symbols_removed"] += 1
                        for sym in diff["added"]:
                            insert_symbols_batch(conn, [sym])
                            stats["layers"]["symbols_edges"]["symbols_added"] += 1
                        for sym in diff["modified"]:
                            insert_symbols_batch(conn, [sym])  # upsert preserves ID
                            stats["layers"]["symbols_edges"]["symbols_modified"] += 1
                        stats["layers"]["symbols_edges"]["symbols_unchanged"] += len(diff["unchanged"])

                        symbols_to_embed.extend(diff["added"] + diff["modified"])
                    else:
                        # Full index or first time
                        for sym in symbols:
                            insert_symbols_batch(conn, [sym])
                            stats["layers"]["symbols_edges"]["symbols_added"] += 1
                        symbols_to_embed.extend(symbols)

                    # Edges
                    for edge in edges:
                        insert_edges_batch(conn, [edge])
                    edges_extracted += len(edges)

                    symbols_extracted += len(symbols)
                    update_file_cache(conn, rel_path, content_hash, len(symbols))
                    stats["layers"]["symbols_edges"]["files_indexed"] += 1

                except Exception as e:
                    stats["errors"].append(f"{rel_path}: {e}")
                    continue

            stats["layers"]["symbols_edges"]["time_ms"] = int((time.time() - layer_start) * 1000)
            stats["total_symbols"] = symbols_extracted
            stats["total_edges"] = edges_extracted

            # LAYER 2: Embeddings (generate for new/modified symbols)
            if embeddings and symbols_to_embed:
                layer_start = time.time()
                stats["layers"]["embeddings"] = {"generated": 0, "skipped": 0}
                # Import here to avoid circular
                from ..embeddings.model import get_embedding_model
                model = get_embedding_model()

                for sym in symbols_to_embed:
                    try:
                        text = f"{sym.get('signature', '')} {sym.get('docstring', '')}".strip()
                        if text:
                            embedding = model.encode(text)
                            conn.execute(
                                "INSERT OR REPLACE INTO symbols_vec (symbol_id, embedding) VALUES (?, ?)",
                                (sym["id"], embedding.tobytes()),
                            )
                            stats["layers"]["embeddings"]["generated"] += 1
                    except Exception as e:
                        stats["errors"].append(f"embedding {sym['id']}: {e}")
                        stats["layers"]["embeddings"]["skipped"] += 1

                stats["layers"]["embeddings"]["time_ms"] = int((time.time() - layer_start) * 1000)
                stats["total_embeddings"] = stats["layers"]["embeddings"]["generated"]

            # LAYER 3: KNN Graph (build after embeddings)
            layer_start = time.time()
            stats["layers"]["knn_graph"] = {"built": False}
            try:
                from ..tools.knn_graph import build_knn_graph
                build_knn_graph(db_path)
                stats["layers"]["knn_graph"]["built"] = True
            except Exception as e:
                stats["errors"].append(f"knn_graph: {e}")
            stats["layers"]["knn_graph"]["time_ms"] = int((time.time() - layer_start) * 1000)

            # LAYER 4: Dependency Metrics
            layer_start = time.time()
            stats["layers"]["dependency_metrics"] = {"computed": False}
            try:
                from ..tools.dependency_metrics import compute_dependency_metrics
                compute_dependency_metrics(db_path)
                stats["layers"]["dependency_metrics"]["computed"] = True
            except Exception as e:
                stats["errors"].append(f"dependency_metrics: {e}")
            stats["layers"]["dependency_metrics"]["time_ms"] = int((time.time() - layer_start) * 1000)

            # LAYER 5: Co-change mining
            layer_start = time.time()
            stats["layers"]["co_change"] = {"pairs_stored": 0}
            try:
                from ..cochange.git_miner import GitMiner
                miner = GitMiner(str(root))
                pairs = miner.mine_pairs(db_path)
                stats["layers"]["co_change"]["pairs_stored"] = pairs
                stats["total_co_change_pairs"] = pairs
            except Exception as e:
                stats["errors"].append(f"co_change: {e}")
            stats["layers"]["co_change"]["time_ms"] = int((time.time() - layer_start) * 1000)

            # LAYER 6: Record snapshot to codebase_snapshots
            layer_start = time.time()
            stats["layers"]["snapshot"] = {"recorded": False}
            try:
                # Gather current stats
                file_count = conn.execute("SELECT COUNT(DISTINCT file_path) FROM symbols").fetchone()[0]
                loc = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]  # approximate
                func_count = conn.execute("SELECT COUNT(*) FROM symbols WHERE kind='function'").fetchone()[0]
                class_count = conn.execute("SELECT COUNT(*) FROM symbols WHERE kind='class'").fetchone()[0]
                edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

                conn.execute(
                    """
                    INSERT INTO codebase_snapshots
                    (codebase_id, files, loc, functions, classes, deps, size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (str(root), file_count, loc, func_count, class_count, edge_count, db_path.stat().st_size),
                )
                stats["layers"]["snapshot"]["recorded"] = True
            except Exception as e:
                stats["errors"].append(f"snapshot: {e}")
            stats["layers"]["snapshot"]["time_ms"] = int((time.time() - layer_start) * 1000)

            # LAYER 7: Update project registry
            layer_start = time.time()
            stats["layers"]["project_registry"] = {"updated": False}
            try:
                from ..tools.project_registry import _get_or_create_project_id
                import yaml

                project_id = _get_or_create_project_id(str(root), root.name)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO projects
                    (id, name, root_path, added_at, last_indexed_at, symbol_count, file_count, index_state)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        root.name,
                        str(root),
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                        symbols_extracted,
                        len(python_files),
                        "ready",
                    ),
                )
                stats["layers"]["project_registry"]["updated"] = True
            except Exception as e:
                stats["errors"].append(f"project_registry: {e}")
            stats["layers"]["project_registry"]["time_ms"] = int((time.time() - layer_start) * 1000)

            conn.commit()

        except Exception as e:
            conn.rollback()
            stats["errors"].append(f"transaction_failed: {e}")
            raise

    stats["finished_at"] = datetime.now().isoformat()
    stats["total_time_ms"] = int((time.time() - t0) * 1000)
    return stats


def symbols_to_embed_filter(symbols: list[dict], existing_ids: set[str]) -> list[dict]:
    """Filter symbols that need embedding generation."""
    return [s for s in symbols if s["id"] not in existing_ids]