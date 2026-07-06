"""Tests for ast_tools.agent_integration token_tracker module."""

from ast_tools.agent_integration.token_tracker import ContextPressureMonitor, TokenTracker


class TestTokenTracker:
    def test_default_budget_not_exceeded(self):
        tracker = TokenTracker()
        result = tracker.track("ast_grep", "small result")
        assert result is None  # within budget

    def test_budget_exceeded(self):
        tracker = TokenTracker(budgets={"ast_grep": 100})
        result = tracker.track("ast_grep", "x" * 1000)
        assert result is not None
        assert result["exceeded"]

    def test_unknown_tool_returns_none(self):
        tracker = TokenTracker()
        result = tracker.track("unknown_tool", "x" * 10000)
        assert result is None

    def test_mcp_prefixed_tool(self):
        tracker = TokenTracker(budgets={"ast_grep": 100})
        result = tracker.track("mcp_ast_tools_tool_ast_grep", "x" * 1000)
        assert result is not None
        assert result["exceeded"]

    def test_custom_budgets(self):
        budgets = {"semantic_search": 500, "default": 100}
        tracker = TokenTracker(budgets)
        result = tracker.track("semantic_search", "x" * 3000)
        assert result is not None
        assert result["budget"] == 500


class TestContextPressureMonitor:
    def test_low_pressure_returns_none(self):
        monitor = ContextPressureMonitor()
        messages = [{"content": "hello"}]
        result = monitor.check_pressure("test-model", messages)
        assert result is None

    def test_high_pressure_returns_warning(self):
        monitor = ContextPressureMonitor({
            "context_window": {"default": 1000, "compression_threshold_ratio": 0.5, "warning_threshold_ratio": 0.4},
            "token_estimation": {"chars_per_token": 4.0},
        })
        # 1600 chars = 400 tokens
        # threshold = 500 (50% of 1000), warning_at = 400 (500 * 0.4/0.5)
        # 400 tokens >= 400 → warning triggers
        messages = [{"content": "x" * 1600}]
        result = monitor.check_pressure("test-model", messages)
        assert result is not None
        assert "Context Pressure" in result["context"]

    def test_empty_history_returns_none(self):
        monitor = ContextPressureMonitor()
        result = monitor.check_pressure("test-model", [])
        assert result is None

    def test_estimate_tokens(self):
        text = "hello world " * 100  # 1200 chars
        est = ContextPressureMonitor.estimate_tokens(text)
        assert est == 300  # 1200 / 4
