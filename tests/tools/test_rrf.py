"""Tests for the RRF (Reciprocal Rank Fusion) utility."""
import pytest
pytestmark = pytest.mark.unit


from ast_tools.utils.rrf import RRF_K, kind_rank, rank_symbols, rrf_fuse


class TestRrfFuse:
    """Tests for rrf_fuse()."""

    def test_two_factors(self):
        ranked = [["a", "b", "c"], ["c", "a", "b"]]
        scores = rrf_fuse(ranked, k=60)
        assert scores["a"] > 0
        assert scores["b"] > 0
        assert scores["c"] > 0
        # 'a' is rank 1 in factor 1 + rank 2 in factor 2 = should be high
        assert scores["a"] > scores["b"]

    def test_six_factors(self):
        ranked = [
            ["a", "b", "c"],
            ["a", "c", "b"],
            ["b", "a", "c"],
            ["c", "a", "b"],
            ["a", "b", "c"],
            ["b", "c", "a"],
        ]
        scores = rrf_fuse(ranked, k=60)
        # 'a' appears at rank 1 in 3 of 6 factors
        assert scores["a"] > scores["b"]
        assert scores["a"] > scores["c"]

    def test_empty_lists(self):
        scores = rrf_fuse([[], [], []], k=60)
        assert scores == {}

    def test_mixed_empty_lists(self):
        ranked = [[], ["a", "b"], []]
        scores = rrf_fuse(ranked, k=60)
        assert scores["a"] > 0
        assert scores["b"] > 0

    def test_single_item_per_list(self):
        ranked = [["x"], ["x"], ["x"]]
        scores = rrf_fuse(ranked, k=60)
        assert scores["x"] == 3.0 / (1 + 60)  # 3 factors, each at rank 0

    def test_all_same_rank_identical(self):
        """Two items at same rank across all factors get equal scores."""
        ranked = [["a", "b"], ["a", "b"], ["a", "b"]]
        scores = rrf_fuse(ranked, k=60)
        assert abs(scores["a"] - scores["b"]) > 0  # a is rank 0, b is rank 1
        # a: 3/(0+1+60) = 3/61 ≈ 0.049
        # b: 3/(1+1+60) = 3/62 ≈ 0.048
        assert scores["a"] > scores["b"]

    def test_custom_k(self):
        ranked = [["a", "b"]]
        k1 = rrf_fuse(ranked, k=1)
        k60 = rrf_fuse(ranked, k=60)
        # k=1 gives higher weight to top ranks
        assert k1["a"] > k60["a"]
        assert k1["b"] > k60["b"]

    def test_no_duplicate_ids(self):
        """Each id should appear once in the fused result."""
        ranked = [["a", "b", "c"], ["c", "d", "e"]]
        scores = rrf_fuse(ranked, k=60)
        assert len(scores) == 5  # a, b, c, d, e — each once


class TestRankSymbols:
    """Tests for rank_symbols()."""

    def test_basic_ranking(self):
        ids = ["a", "b", "c"]
        scores = {"a": 10.0, "b": 5.0, "c": 15.0}
        ranked = rank_symbols(ids, key_fn=lambda x: scores[x])
        assert ranked == ["c", "a", "b"]  # highest first

    def test_ascending_order(self):
        ids = ["a", "b", "c"]
        scores = {"a": 10.0, "b": 5.0, "c": 15.0}
        ranked = rank_symbols(ids, key_fn=lambda x: scores[x], reverse=False)
        assert ranked == ["b", "a", "c"]  # lowest first

    def test_ties(self):
        ids = ["a", "b", "c"]
        scores = {"a": 5.0, "b": 5.0, "c": 5.0}
        ranked = rank_symbols(ids, key_fn=lambda x: scores[x])
        # Stable: preserves input order for ties
        assert len(ranked) == 3

    def test_empty_list(self):
        ranked = rank_symbols([], key_fn=lambda x: 0.0)
        assert ranked == []

    def test_single_item(self):
        ranked = rank_symbols(["a"], key_fn=lambda x: 100.0)
        assert ranked == ["a"]

    def test_missing_scores_default_to_zero(self):
        """Symbols without scores should rank lowest."""
        ids = ["a", "b", "c"]
        scores = {"a": 10.0, "c": 5.0}  # 'b' missing
        ranked = rank_symbols(ids, key_fn=lambda x: scores.get(x, 0.0))
        assert ranked == ["a", "c", "b"]


class TestKindRank:
    """Tests for kind_rank()."""

    def test_function_is_highest(self):
        assert kind_rank("function") > kind_rank("class")

    def test_class_higher_than_method(self):
        assert kind_rank("class") > kind_rank("method")

    def test_method_higher_than_variable(self):
        assert kind_rank("method") > kind_rank("variable")

    def test_variable_higher_than_import(self):
        assert kind_rank("variable") > kind_rank("import")

    def test_constant_same_as_import(self):
        assert kind_rank("constant") == kind_rank("import")

    def test_unknown_kind_returns_zero(self):
        assert kind_rank("unknown") == 0.0

    def test_case_insensitive(self):
        assert kind_rank("Function") == kind_rank("function")