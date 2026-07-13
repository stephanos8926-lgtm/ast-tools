"""Tests for the llm_suggest_fix MCP tool."""

from ast_tools.tools import list_tool_names, get_tool_handler, get_tool_schema


class TestToolRegistration:
    """Test the tool is properly registered."""

    def test_tool_registered(self):
        """Tool appears in the registry."""
        names = list_tool_names()
        assert "llm_suggest_fix" in names

    def test_tool_handler_callable(self):
        """Handler is a callable function."""
        handler = get_tool_handler("llm_suggest_fix")
        assert callable(handler)

    def test_tool_schema_exists(self):
        """Tool has a schema registered."""
        schema = get_tool_schema("llm_suggest_fix")
        assert schema is not None
        assert "description" in schema
        assert "inputSchema" in schema
        input_schema = schema["inputSchema"]
        assert "properties" in input_schema
        assert "code" in input_schema["properties"]
        assert "diagnostic" in input_schema["properties"]
        assert "required" in input_schema

    def test_tool_schema_required_fields(self):
        """Required fields include code and diagnostic."""
        schema = get_tool_schema("llm_suggest_fix")
        required = schema["inputSchema"]["required"]
        assert "code" in required
        assert "diagnostic" in required


class TestToolBehavior:
    """Test tool handler behavior with mocked LLMClient."""

    def test_returns_error_for_missing_code(self):
        """Missing required 'code' param returns error."""
        from ast_tools.tools.llm_suggest_fix import _tool_llm_suggest_fix

        result = _tool_llm_suggest_fix("llm_suggest_fix", {"diagnostic": "test"})
        assert "error" in result
        assert "code" in result.get("error", "").lower()

    def test_returns_error_for_missing_diagnostic(self):
        """Missing required 'diagnostic' param returns error."""
        from ast_tools.tools.llm_suggest_fix import _tool_llm_suggest_fix

        result = _tool_llm_suggest_fix("llm_suggest_fix", {"code": "x = 1"})
        assert "error" in result
        assert "diagnostic" in result.get("error", "").lower()
