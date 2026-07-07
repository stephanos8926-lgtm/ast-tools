"""Tests for ContextInjector - relevance scoring, budget management, diversity."""

import pytest

pytestmark = pytest.mark.unit


import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from ast_tools.context.injector import ContextInjector, Symbol


class TestRelevanceScoring:
    """Test multi-factor relevance scoring."""

    def test_calculate_semantic_score(self):
        """Test semantic similarity scoring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(Path(tmpdir))

            query_emb = np.array([1.0, 0.0, 0.0])
            symbol_emb = np.array([0.8, 0.2, 0.0])

            score = injector._calculate_semantic_similarity(query_emb, symbol_emb)

            assert 0.0 <= score <= 1.0
            assert score > 0.7  # Should be high similarity

    def test_calculate_recency_score(self):
        """Test recency scoring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(Path(tmpdir))

            # Fresh file (today)
            fresh_date = datetime.now()
            score_fresh = injector._calculate_recency_score(fresh_date)
            assert score_fresh > 0.9

            # Old file (30 days ago)
            old_date = datetime.now() - timedelta(days=30)
            score_old = injector._calculate_recency_score(old_date)
            assert score_old < score_fresh
            assert score_old > 0.0  # Never zero

    def test_calculate_usage_score(self):
        """Test usage frequency scoring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(Path(tmpdir))

            # High usage
            score_high = injector._calculate_usage_score(ref_count=100, max_refs=100)
            assert score_high > 0.8

            # Low usage
            score_low = injector._calculate_usage_score(ref_count=5, max_refs=100)
            assert score_low < score_high

    def test_kind_boost(self):
        """Test kind-based scoring boost."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(Path(tmpdir))

            # Class/function should get boost
            score_class = injector._calculate_kind_boost("class")
            score_function = injector._calculate_kind_boost("function")
            assert score_class > 0.8
            assert score_function > 0.8

            # Variable should get less
            score_var = injector._calculate_kind_boost("variable")
            assert score_var < 0.6

    def test_proximity_score(self):
        """Test file proximity scoring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(Path(tmpdir))

            # Same file
            score = injector._calculate_proximity_score(
                "/home/project/src/main.py", "/home/project/src/main.py"
            )
            assert score == 1.0

            # Different file
            score = injector._calculate_proximity_score(
                "/home/project/src/other.py", "/home/project/src/main.py"
            )
            assert 0.0 <= score < 1.0

    def test_combined_relevance_score(self):
        """Test combined relevance score with all factors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            injector = ContextInjector(Path(tmpdir))

            symbol = Symbol(
                id="sym-1",
                name="MyClass",
                kind="class",
                file_path="/home/project/src/main.py",
                line=10,
                signature="class MyClass:",
                docstring="A test class",
                embedding=np.array([1.0, 0.0, 0.0]),
                references_count=50,
                last_indexed=datetime.now().isoformat(),
            )

            query_emb = np.array([1.0, 0.0, 0.0])
            score = injector.calculate_relevance_score(
                symbol, query_embedding=query_emb, current_file="/home/project/src/main.py"
            )

            assert 0.0 <= score <= 1.0
            # High semantic (perfect match) + kind boost + proximity + recency
            assert score > 0.7
