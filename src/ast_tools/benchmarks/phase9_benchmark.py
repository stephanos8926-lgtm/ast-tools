#!/usr/bin/env python3
"""Performance benchmarks for Phase 9 features.

Tests:
1. Dependency metrics computation (PageRank, fan-in/out)
2. KNN graph build time
3. Similarity query latency
4. Audit log write throughput
5. Index effectiveness

Usage:
    python3 src/ast_tools/benchmarks/phase9_benchmark.py
"""

import sqlite3
import time
import random
import statistics
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_test_data(conn: sqlite3.Connection, num_symbols: int = 1000):
    """Generate test symbols and edges for benchmarking."""
    logger.info(f"Generating {num_symbols} test symbols...")
    
    # Create symbols
    symbols = []
    for i in range(num_symbols):
        symbol_id = f"test_{i:05d}"
        symbols.append((symbol_id, f"func_{i}", f"module{i}.func_{i}", "function", f"file{i}.py"))
    
    with conn:
        conn.executemany("""
            INSERT OR IGNORE INTO symbols (id, name, qualified_name, kind, file_path)
            VALUES (?, ?, ?, ?, ?)
        """, symbols)
    
    logger.info(f"Generated {num_symbols} symbols")
    
    # Create edges (dense graph for stress test)
    logger.info("Generating test edges...")
    edges = []
    for i in range(num_symbols):
        # Each symbol calls 3-10 others
        num_calls = random.randint(3, 10)
        targets = random.sample(range(num_symbols), min(num_calls, num_symbols - 1))
        for j in targets:
            if i != j:  # No self-calls
                edges.append((f"test_{i:05d}", f"test_{j:05d}", "calls"))
    
    with conn:
        conn.executemany("""
            INSERT OR IGNORE INTO edges (source_id, target_id, edge_type)
            VALUES (?, ?, ?)
        """, edges)
    
    logger.info(f"Generated {len(edges)} edges")
    return len(edges)


def benchmark_dependency_metrics(conn: sqlite3.Connection) -> dict:
    """Benchmark dependency metrics computation."""
    from src.ast_tools.indexer.dependency_metrics import DependencyMetricsCalculator
    
    logger.info("Benchmarking dependency metrics...")
    calc = DependencyMetricsCalculator()
    
    # Load edges
    start = time.time()
    calc.load_from_database(conn)
    load_time = time.time() - start
    
    # Compute metrics
    start = time.time()
    metrics = calc.compute_all_metrics()
    compute_time = time.time() - start
    
    logger.info(f"Computed metrics for {len(metrics)} symbols in {compute_time:.3f}s")
    
    return {
        "load_time": load_time,
        "compute_time": compute_time,
        "symbols_per_second": len(metrics) / compute_time if compute_time > 0 else float('inf')
    }


def benchmark_knn_build(num_items: int = 500, dim: int = 384) -> dict:
    """Benchmark KNN graph build time."""
    try:
        from src.ast_tools.indexer.knn_builder import KNNGraphBuilder
    except ImportError:
        logger.warning("hnswlib not available - skipping KNN benchmark")
        return {"status": "skipped", "reason": "hnswlib not installed"}
    
    logger.info(f"Benchmarking KNN build with {num_items} items...")
    builder = KNNGraphBuilder(dim=dim)
    
    # Generate random embeddings
    embeddings = [[random.random() for _ in range(dim)] for _ in range(num_items)]
    
    start = time.time()
    for i, emb in enumerate(embeddings):
        builder.add_item(f"item_{i}", emb)
    build_time = time.time() - start
    
    builder.build()
    
    # Benchmark query
    query_emb = embeddings[0]
    start = time.time()
    results = builder.query(query_emb, k=10)
    query_time = time.time() - start
    
    logger.info(f"Built KNN index in {build_time:.3f}s, query in {query_time*1000:.2f}ms")
    
    return {
        "build_time": build_time,
        "query_time_ms": query_time * 1000,
        "items_per_second": num_items / build_time if build_time > 0 else float('inf')
    }


def benchmark_audit_log_writes(conn: sqlite3.Connection, num_writes: int = 1000) -> dict:
    """Benchmark audit log write throughput."""
    from src.ast_tools.utils.secret_sanitizer import log_audit_event
    
    logger.info(f"Benchmarking audit log writes ({num_writes} writes)...")
    
    start = time.time()
    for i in range(num_writes):
        log_audit_event(
            conn,
            user=f"user_{i % 10}",
            action=random.choice(["query", "index", "search", "export"]),
            resource=f"symbol_{i}",
            details={"query": f"test_{i}", "api_key": "sk-test123"},  # Test sanitization
            result="success"
        )
    total_time = time.time() - start
    
    writes_per_second = num_writes / total_time if total_time > 0 else float('inf')
    logger.info(f"Wrote {num_writes} audit logs in {total_time:.3f}s ({writes_per_second:.0f}/s)")
    
    return {
        "total_time": total_time,
        "writes_per_second": writes_per_second,
        "sanitization_overhead": "included"
    }


def benchmark_index_effectiveness(conn: sqlite3.Connection) -> dict:
    """Benchmark query performance with indexes."""
    logger.info("Benchmarking index effectiveness...")
    
    results = {}
    
    # Test 1: Query by source_id (should use index)
    start = time.time()
    for _ in range(100):
        conn.execute("SELECT * FROM edges WHERE source_id = ?", ("test_00001",)).fetchall()
    results["edges_by_source"] = (time.time() - start) * 10  # ms per query
    
    # Test 2: Query by edge_type (should use composite index)
    start = time.time()
    for _ in range(100):
        conn.execute("SELECT * FROM edges WHERE edge_type = ?", ("calls",)).fetchall()
    results["edges_by_type"] = (time.time() - start) * 10
    
    # Test 3: High SPOF symbols (should use index)
    start = time.time()
    for _ in range(100):
        conn.execute("SELECT * FROM dependency_metrics WHERE spof_score > ?", (0.5,)).fetchall()
    results["high_spof"] = (time.time() - start) * 10
    
    # Test 4: Audit log by timestamp
    start = time.time()
    for _ in range(100):
        conn.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 10").fetchall()
    results["audit_recent"] = (time.time() - start) * 10
    
    for query, time_ms in results.items():
        logger.info(f"  {query}: {time_ms:.2f}ms")
    
    return results


def run_benchmarks(db_path: str = ":memory:", cleanup: bool = True):
    """Run all benchmarks."""
    import tempfile
    import os
    
    # Use temp file for realistic I/O
    if db_path == ":memory:":
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        cleanup = True
    
    logger.info("="*60)
    logger.info("Phase 9 Performance Benchmarks")
    logger.info("="*60)
    
    conn = sqlite3.connect(db_path)
    results = {}
    
    try:
        # Setup schema
        logger.info("Setting up schema...")
        from src.ast_tools.database.schema import init_db, get_db_connection
        from src.ast_tools.database.migrations import run_migrations
        init_db(db_path)
        run_migrations(db_path)
        logger.info("Schema initialized")
        
        # Generate test data
        num_edges = generate_test_data(conn, num_symbols=1000)
        results["test_data"] = {"symbols": 1000, "edges": num_edges}
        
        # Run benchmarks
        results["dependency_metrics"] = benchmark_dependency_metrics(conn)
        results["knn_build"] = benchmark_knn_build(num_items=500)
        results["audit_writes"] = benchmark_audit_log_writes(conn, num_writes=1000)
        results["index_effectiveness"] = benchmark_index_effectiveness(conn)
        
        # Summary
        logger.info("="*60)
        logger.info("BENCHMARK SUMMARY")
        logger.info("="*60)
        for name, metrics in results.items():
            logger.info(f"\n{name}:")
            for key, value in metrics.items():
                if isinstance(value, float):
                    logger.info(f"  {key}: {value:.3f}")
                else:
                    logger.info(f"  {key}: {value}")
        
        return results
    
    finally:
        conn.close()
        if cleanup and os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    run_benchmarks()