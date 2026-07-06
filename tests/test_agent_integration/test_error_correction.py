"""Tests for ast_tools.agent_integration error_correction module."""

from ast_tools.agent_integration import correct_tool_error, get_error_correction


class TestErrorCorrection:
    def test_ast_edit_invalid_operation(self):
        result = correct_tool_error("ast_edit", "Error: Invalid operation")
        assert result is not None
        assert "dry_run" in result["context"]

    def test_ast_edit_dry_run(self):
        result = correct_tool_error("ast_edit", "Error: dry_run is required")
        assert result is not None
        assert "dry_run" in result["context"]

    def test_semantic_search_no_results(self):
        result = correct_tool_error("semantic_search", "Error: no results")
        # "no results" triggers correction for semantic_search
        assert result is not None
        assert "query" in result["context"].lower()

    def test_impact_analysis_symbol_not_found(self):
        result = correct_tool_error("impact_analysis", "Error: symbol not found")
        assert result is not None
        assert "find_references" in result["context"]

    def test_successful_result_no_error(self):
        result = correct_tool_error("ast_edit", "Success: file updated")
        assert result is None

    def test_unknown_tool_returns_none(self):
        result = correct_tool_error("unknown_tool", "Error: something failed")
        assert result is None

    def test_mcp_prefixed_tool(self):
        result = correct_tool_error(
            "mcp_ast_tools_tool_ast_edit",
            "Error: Invalid operation",
        )
        assert result is not None
        assert "dry_run" in result["context"]

    def test_get_error_correction_direct(self):
        corr = get_error_correction("ast_grep", "Error: Invalid pattern")
        assert corr is not None
        assert "$$$" in corr  # mentions multi-node syntax

    def test_no_error_in_result(self):
        corr = get_error_correction("ast_grep", "Found 5 matches")
        assert corr is None
