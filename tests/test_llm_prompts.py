"""Tests for LLM prompt templates."""

from ast_tools.llm.prompts import Prompts


class TestFixSuggestion:
    """Tests for Prompts.fix_suggestion()."""

    def test_contains_diagnostic_code(self):
        prompt = Prompts.fix_suggestion(
            code="x = 1\n",
            diagnostic_message="Unused variable 'x'",
            diagnostic_code="F841",
            file_path="test.py",
            language="python",
        )
        assert "F841" in prompt
        assert "Unused variable" in prompt

    def test_contains_code_context(self):
        prompt = Prompts.fix_suggestion(
            code="x = 1\n",
            diagnostic_message="Test",
            diagnostic_code="E001",
            file_path="test.py",
            language="python",
        )
        assert "x = 1" in prompt
        assert "```python" in prompt

    def test_contains_diff_instruction(self):
        prompt = Prompts.fix_suggestion(
            code="x = 1\n",
            diagnostic_message="Test",
            diagnostic_code="E001",
            file_path="test.py",
            language="python",
        )
        assert "unified diff" in prompt.lower()

    def test_truncates_long_code(self):
        code = "x = 1\n" * 5000
        prompt = Prompts.fix_suggestion(
            code=code,
            diagnostic_message="Test",
            diagnostic_code="E001",
            file_path="test.py",
            language="python",
        )
        # Should not exceed ~10K chars (6000 code + template overhead)
        assert len(prompt) < 10000
        assert "[truncated]" in prompt

    def test_short_code_not_truncated(self):
        code = "x = 1\n"
        prompt = Prompts.fix_suggestion(
            code=code,
            diagnostic_message="Test",
            diagnostic_code="E001",
            file_path="test.py",
            language="python",
        )
        assert "[truncated]" not in prompt

    def test_different_language(self):
        prompt = Prompts.fix_suggestion(
            code="let x = 1;\n",
            diagnostic_message="Unused variable",
            diagnostic_code="TS-01",
            file_path="test.ts",
            language="typescript",
        )
        assert "```typescript" in prompt
        assert "test.ts" in prompt
