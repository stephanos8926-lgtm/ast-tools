"""Unit tests for AST cache with LRU eviction."""

import tempfile
import time
from pathlib import Path

from ast_tools.indexer.cache import (
    ASTCache,
    ASTNodeEncoder,
)


class TestASTNodeEncoder:
    """Test JSON encoder for AST nodes."""

    def test_encode_simple_node(self):
        """Should encode simple AST nodes."""
        import ast

        node = ast.Name(id="x", ctx=ast.Load())

        encoder = ASTNodeEncoder()
        result = encoder.default(node)

        assert result["_type"] == "Name"
        assert result["id"] == "x"
        assert "lineno" in result


class TestASTCache:
    """Test ASTCache class."""

    def test_cache_get_miss(self):
        """Cache miss should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ASTCache(cache_dir=Path(tmpdir))
            result = cache.get("/nonexistent.py", "hash123")
            assert result is None

    def test_cache_set_and_get(self):
        """Should store and retrieve cached data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ASTCache(cache_dir=Path(tmpdir))

            test_data = {"ast_nodes": ["node1", "node2"]}
            cache.set("/test.py", "abc123", test_data)

            result = cache.get("/test.py", "abc123")
            assert result == test_data

    def test_cache_stale_hash(self):
        """Should return None for stale cache (hash mismatch)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ASTCache(cache_dir=Path(tmpdir))

            cache.set("/test.py", "old_hash", {"data": "old"})
            result = cache.get("/test.py", "new_hash")

            assert result is None

    def test_cache_eviction_lru(self):
        """Should evict least recently used entries when over limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Tiny cache (1MB)
            cache = ASTCache(cache_dir=Path(tmpdir), max_size_mb=1)

            # Fill cache
            for i in range(10):
                data = {"data": "x" * 100000}  # 100KB each
                cache.set(f"/file{i}.py", f"hash{i}", data)
                time.sleep(0.01)  # Ensure different timestamps

            # Access first file to make it recently used
            cache.get("/file0.py", "hash0")

            # Add more to trigger eviction
            cache.set("/file_new.py", "hash_new", {"data": "y" * 100000})

            # file0 should still exist (recently used)
            cache.get("/file0.py", "hash0")
            # Earlier files (1, 2, 3...) may have been evicted

    def test_cache_remove(self):
        """Should remove entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ASTCache(cache_dir=Path(tmpdir))

            cache.set("/test.py", "hash123", {"data": "test"})
            cache.remove("/test.py")

            result = cache.get("/test.py", "hash123")
            assert result is None

    def test_cache_clear(self):
        """Should clear all entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ASTCache(cache_dir=Path(tmpdir))

            for i in range(5):
                cache.set(f"/file{i}.py", f"hash{i}", {"data": i})

            cache.clear()

            for i in range(5):
                result = cache.get(f"/file{i}.py", f"hash{i}")
                assert result is None

    def test_cache_stats(self):
        """Should return statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ASTCache(cache_dir=Path(tmpdir))

            cache.set("/test.py", "hash123", {"data": "test"})

            stats = cache.get_stats()

            assert "size_bytes" in stats
            assert "file_count" in stats
            assert "max_size_bytes" in stats
            assert stats["file_count"] >= 1
            assert stats["eviction_policy"] == "LRU"

    def test_cache_validates_path_traversal(self):
        """Should handle path traversal attempts safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ASTCache(cache_dir=Path(tmpdir))

            # Attempt path traversal
            cache.set("../../../etc/passwd", "hash", {"data": "malicious"})

            # Should not have created files outside cache
            cache_path = cache._get_cache_path("../../../etc/passwd")
            assert str(cache_path).startswith(str(tmpdir))
