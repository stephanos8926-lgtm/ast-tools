"""Tests for Phase 8B: ContextInjector integration into semantic_search MCP tool."""

import pytest
import numpy as np
from pathlib import Path
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import sqlite3

# Import the semantic_search module and ContextInjector
from src.ast_tools.tools.semantic_search import (
    hybrid_search_with_context,
    select_context_with_budget,
    estimate_context_tokens,
    format_context_result,
    fallback_search,
)
from src.ast_tools.context.injector import ContextInjector, Symbol
from src.ast_tools.context.formatters import MarkdownFormatter


class TestContextInjectionIntegration:
    """Test ContextInjector integration with semantic search."""

    def test_hybrid_search_with_context_returns_symbols_and_context(self):
        """Test that hybrid search with context returns both search results and formatted context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            # Create a mock connection
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            
            # Initialize schema
            from src.ast_tools.database.schema import init_schema
            init_schema(conn)
            
            # Insert test symbols
            conn.execute("""
                INSERT INTO symbols (id, name, qualified_name, kind, file_path, start_line, end_line, signature, docstring, is_public, content_hash, indexed_at, lang)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "sym-1", "MyClass", "mymodule.MyClass", "class", 
                "/project/src/main.py", 10, 50, "class MyClass:", "A test class",
                1, "hash123", int(datetime.now().timestamp()), "python"
            ))
            
            conn.commit()
            
            # Test the function
            results, context_injection = hybrid_search_with_context(
                conn, 
                "test class",
                k=5,
                context_enabled=True,
                max_context_symbols=3
            )
            
            assert isinstance(results, list)
            assert isinstance(context_injection, dict)
            assert "context_markdown" in context_injection
            assert "tokens_used" in context_injection
            assert "budget_remaining" in context_injection
            
            conn.close()

    def test_select_context_with_budget_enforcement(self):
        """Test that context selection respects token budget."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            injector = ContextInjector(db_path, model_context_window=8000, max_context_symbols=10)
            
            # Create symbols with varying estimated token counts
            symbols = [
                {
                    "id": f"sym-{i}",
                    "name": f"Symbol{i}",
                    "kind": "function",
                    "file_path": f"file{i % 3}.py",
                    "start_line": i,
                    "signature": f"def func{i}(): " + "x" * 100,  # Varying signature lengths
                    "docstring": f"Docstring {i}" if i % 2 == 0 else None,
                }
                for i in range(10)
            ]
            
            selected, tokens_used = select_context_with_budget(
                symbols,
                injector,
                max_tokens=1500,
                existing_context_tokens=2000,
                k=5
            )
            
            # Should respect budget
            assert tokens_used <= 1500
            assert len(selected) <= 5
            
            # Should enforce diversity (max 3 per file)
            from collections import Counter
            file_counts = Counter(s["file_path"] for s in selected)
            assert all(count <= 3 for count in file_counts.values())

    def test_estimate_context_tokens_accuracy(self):
        """Test token estimation for context symbols."""
        symbol_short = {
            "id": "sym-1",
            "name": "short",
            "signature": "def short():",
            "docstring": None
        }
        
        symbol_long = {
            "id": "sym-2",
            "name": "long",
            "signature": "def long_function_with_many_parameters(a, b, c, d, e): " + "x" * 200,
            "docstring": "This is a very long docstring\n" * 10
        }
        
        tokens_short = estimate_context_tokens(symbol_short)
        tokens_long = estimate_context_tokens(symbol_long)
        
        assert tokens_short > 0
        assert tokens_long > tokens_short
        assert tokens_long < 2000  # Should be capped

    def test_format_context_result_markdown(self):
        """Test formatting of context injection results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            injector = ContextInjector(db_path)
            
            symbols = [{
                "id": "sym-1",
                "name": "MyClass",
                "kind": "class",
                "file_path": "/project/src/main.py",
                "start_line": 10,
                "signature": "class MyClass:",
                "docstring": "A test class",
                "relevance_score": 0.85,
            }]
            
            formatted = format_context_result(
                symbols,
                tokens_used=300,
                tokens_budget=2000,
                model_context_window=32000,
                max_symbols=5
            )
            
            assert isinstance(formatted, str)
            assert "MyClass" in formatted
            assert "main.py:10" in formatted
            assert "Relevance:" in formatted


class TestDiversitySelection:
    """Test diversity enforcement in context selection."""

    def test_diversity_limits_symbols_per_file(self):
        """Test that diversity limit enforces max symbols per file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            injector = ContextInjector(db_path, diversity_limit=2)
            
            # All symbols from same file
            symbols = [
                {
                    "id": f"sym-{i}",
                    "name": f"Func{i}",
                    "kind": "function",
                    "file_path": "same_file.py",
                    "start_line": i,
                    "signature": f"def f{i}():",
                    "docstring": None,
                    "relevance_score": 0.9 - (i * 0.05),  # Decreasing scores
                }
                for i in range(10)
            ]
            
            # Manually set relevance scores for sorting
            for sym in symbols:
                sym["relevance_score"] = injector.calculate_relevance_score(
                    type('Symbol', (), {
                        "id": sym["id"],
                        "kind": sym["kind"],
                        "file_path": sym["file_path"],
                        "embedding": np.random.rand(384),
                        "references_count": i,
                        "last_indexed": datetime.now().isoformat()
                    })()
                )
            
            selected, _ = select_context_with_budget(
                symbols,
                injector,
                max_tokens=5000,
                existing_context_tokens=0,
                k=10,
                diversity_limit=2
            )
            
            # Should be limited to diversity_limit
            assert len(selected) <= 2


class TestSqliteVecIntegration:
    """Test sqlite-vec embeddings integration."""

    def test_search_similar_returns_distances(self):
        """Test that vector search returns symbol IDs with distances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            
            # Initialize schema with vec table
            from src.ast_tools.database.schema import init_schema
            from src.ast_tools.embeddings.store import load_vec_extension
            
            init_schema(conn)
            
            # Load vec extension
            try:
                load_vec_extension(conn)
                
                # Insert test symbol
                conn.execute("""
                    INSERT INTO symbols (id, name, qualified_name, kind, file_path, start_line, end_line, signature, docstring, is_public, content_hash, indexed_at, lang)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "sym-1", "TestFunc", "test.func", "function",
                    "/test.py", 1, 10, "def test():", "Test function",
                    1, "hash123", int(datetime.now().timestamp()), "python"
                ))
                
                # Insert embedding
                test_embedding = np.random.rand(384).tolist()
                query_embedding = test_embedding.copy()  # Identical for high similarity
                
                from src.ast_tools.embeddings.store import insert_embedding, search_similar
                insert_embedding(conn, "sym-1", test_embedding)
                
                results = search_similar(conn, query_embedding, k=5)
                
                # Should return (symbol_id, distance) tuples
                assert len(results) > 0
                symbol_id, distance = results[0]
                assert symbol_id == "sym-1"
                assert 0.0 <= distance <= 2.0  # Cosine distance range
                
            except ImportError:
                # sqlite-vec not installed, skip test
                pytest.skip("sqlite-vec not installed")
            
            conn.close()

    def test_fallback_when_vec_not_available(self):
        """Test graceful fallback when sqlite-vec is unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            
            from src.ast_tools.database.schema import init_schema
            init_schema(conn)
            
            # Insert test symbol but NO embedding
            conn.execute("""
                INSERT INTO symbols (id, name, qualified_name, kind, file_path, start_line, end_line, signature, docstring, is_public, content_hash, indexed_at, lang)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "sym-1", "TestFunc", "test.func", "function",
                "/test.py", 1, 10, "def test():", "Test function",
                1, "hash123", int(datetime.now().timestamp()), "python"
            ))
            
            conn.commit()
            
            # Test fallback search (should use FTS5 only)
            query = "test function"
            results = fallback_search(conn, query, k=5)
            
            # Should return results from FTS5
            assert isinstance(results, list)
            
            conn.close()


class TestTokenBudgetEnforcement:
    """Test token budget management."""

    def test_respects_model_context_window(self):
        """Test that budget calculation respects context window."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            # Small context window
            injector = ContextInjector(db_path, model_context_window=4000)
            
            available = injector.calculate_available_budget(
                existing_context_tokens=2000
            )
            
            # Should account for protected messages buffer
            assert available < 2000
            assert available > 0

    def test_budget_zero_when_full(self):
        """Test that budget is zero when context is full."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            
            injector = ContextInjector(db_path, model_context_window=4000)
            
            # Context nearly full
            available = injector.calculate_available_budget(
                existing_context_tokens=3800
            )
            
            assert available == 0


class TestGracefulFallback:
    """Test fallback behavior for error cases."""

    def test_fallback_on_database_error(self):
        """Test graceful handling of database errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            
            # Query without any symbols
            with patch('src.ast_tools.tools.semantic_search.generate_embedding') as mock_emb:
                mock_emb.side_effect = Exception("Model not loaded")
                
                # Should handle error gracefully
                results, context = hybrid_search_with_context(
                    conn,
                    "test query",
                    k=5,
                    context_enabled=True
                )
                
                # Should return empty results, not crash
                assert isinstance(results, list)
                assert "error" in context or len(results) == 0
            
            conn.close()

    def test_empty_result_when_no_matches(self):
        """Test handling of no search results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            
            from src.ast_tools.database.schema import init_schema
            init_schema(conn)
            conn.commit()
            
            # Search in empty database
            results, context = hybrid_search_with_context(
                conn,
                "nonexistent query",
                k=5,
                context_enabled=True
            )
            
            assert results == []
            assert context is not None
            
            conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])