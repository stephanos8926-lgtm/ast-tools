"""Tests for ast_tools.agent_integration context_builder module."""

from ast_tools.agent_integration import build_ast_tools_context, detect_ast_query


class TestDetectAstQuery:
    def test_detects_ast_grep(self):
        assert detect_ast_query("how do I use ast_grep?")

    def test_detects_ast_read(self):
        assert detect_ast_query("show me ast_read output")

    def test_detects_semantic_search(self):
        assert detect_ast_query("semantic search for symbols")

    def test_detects_impact_analysis(self):
        assert detect_ast_query("impact analysis for this file")

    def test_empty_query(self):
        assert not detect_ast_query("")

    def test_unrelated_query(self):
        assert not detect_ast_query("what is the weather today?")

    def test_partial_word_match(self):
        # "ast " requires trailing space to avoid matching "astronomy"
        assert not detect_ast_query("astronomy class")


class TestBuildAstToolsContext:
    def test_returns_string(self):
        ctx = build_ast_tools_context()
        assert isinstance(ctx, str)
        assert len(ctx) > 500

    def test_contains_tool_names(self):
        ctx = build_ast_tools_context("ast grep")
        assert "ast_grep" in ctx
        assert "ast_edit" in ctx
        assert "semantic_search" in ctx

    def test_reasonable_size(self):
        ctx = build_ast_tools_context()
        # Should be under 3000 chars (fits in 1000 tokens)
        assert len(ctx) < 3000, f"Context too large: {len(ctx)} chars"

    def test_query_parameter_accepted(self):
        ctx1 = build_ast_tools_context("")
        ctx2 = build_ast_tools_context("ast grep")
        assert isinstance(ctx1, str)
        assert isinstance(ctx2, str)
