"""Tests for ContextInjector - budget management, selection, diversity."""

import pytest
import numpy as np
from pathlib import Path
import tempfile
from datetime import datetime
from ast_tools.context.injector import ContextInjector, Symbol


class TestBudgetManagement:
    """Test token budget management."""
    
    def test_estimate_tokens(self):
        """Test token estimation per symbol."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(Path(tmpdir))
            
            # Simple function
            symbol_simple = Symbol(
                id="sym-1",
                name="hello",
                kind="function",
                file_path="test.py",
                line=1,
                signature="def hello():",
                docstring=None,
                embedding=None,
                references_count=0,
                last_indexed=datetime.now().isoformat()
            )
            
            tokens = injector.estimate_symbol_tokens(symbol_simple)
            assert tokens > 0
            assert tokens < 500  # Simple function should be small
    
    def test_calculate_available_budget(self):
        """Test budget calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(
                Path(tmpdir),
                model_context_window=32000,
                protect_last_n_messages=2
            )
            
            available = injector.calculate_available_budget(
                existing_context_tokens=5000
            )
            
            # Should reserve some for conversation
            assert available < 27000  # 32000 - 5000 - buffer
            assert available > 0
    
    def test_select_top_k_within_budget(self):
        """Test symbol selection respects budget."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(
                Path(tmpdir),
                max_context_symbols=10
            )
            
            # Create 15 symbols with varying scores
            symbols = [
                Symbol(
                    id=f"sym-{i}",
                    name=f"Symbol{i}",
                    kind="function",
                    file_path=f"file{i % 3}.py",  # 3 files
                    line=i,
                    signature=f"def func{i}():",
                    docstring=f"Docstring {i}",
                    embedding=np.random.rand(384),
                    references_count=i * 2,
                    last_indexed=datetime.now().isoformat()
                )
                for i in range(15)
            ]
            
            selected = injector.select_top_k(symbols, k=10)
            
            # Should respect max_symbols
            assert len(selected) <= 10
            # Should respect diversity (max 3 per file)
            from collections import Counter
            file_counts = Counter(getattr(s, 'file_path') for s in selected)
            assert all(count <= 3 for count in file_counts.values())


class TestDiversityEnforcement:
    """Test diversity constraints."""
    
    def test_diversity_limit_enforced(self):
        """Test max symbols per file limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(
                Path(tmpdir),
                diversity_limit=3
            )
            
            # All symbols from same file
            symbols = [
                Symbol(
                    id=f"sym-{i}",
                    name=f"Func{i}",
                    kind="function",
                    file_path="same_file.py",
                    line=i,
                    signature=f"def f{i}():",
                    docstring=None,
                    embedding=np.random.rand(384),
                    references_count=i,
                    last_indexed=datetime.now().isoformat()
                )
                for i in range(10)
            ]
            
            # Score them first
            for sym in symbols:
                sym.relevance_score = injector.calculate_relevance_score(sym)  # type: ignore
            
            # Sort and select
            sorted_symbols = sorted(symbols, key=lambda s: s.relevance_score, reverse=True)  # type: ignore
            selected = injector.history.enforce_diversity(sorted_symbols, limit=3)
            
            # Should be limited to diversity_limit
            assert len(selected) == 3
    
    def test_diversity_with_multiple_files(self):
        """Test diversity with multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(
                Path(tmpdir),
                diversity_limit=3
            )
            
            # 5 files with 5 symbols each
            symbols = []
            for file_idx in range(5):
                for sym_idx in range(5):
                    symbols.append(
                        Symbol(
                            id=f"sym-{file_idx}-{sym_idx}",
                            name=f"Func{file_idx}_{sym_idx}",
                            kind="function",
                            file_path=f"file{file_idx}.py",
                            line=sym_idx,
                            signature=f"def f{sym_idx}():",
                            docstring=None,
                            embedding=np.random.rand(384),
                            references_count=sym_idx,
                            last_indexed=datetime.now().isoformat()
                        )
                    )
            
            # Score them first
            for sym in symbols:
                sym.relevance_score = injector.calculate_relevance_score(sym)  # type: ignore
            
            selected = injector.select_top_k(symbols, k=15)
            
            # Should get 15 symbols, max 3 from each file
            from collections import Counter
            file_counts = Counter(getattr(s, 'file_path') for s in selected)
            
            assert len(selected) == 15
            assert all(count <= 3 for count in file_counts.values())