"""Token tracker — budget tracking and context pressure monitoring.

Extracted from the Hermes ast-tools-tokens plugin.
Zero Hermes dependency — pure functions usable by any agent framework.

Usage:
    from ast_tools.agent_integration import TokenTracker, ContextPressureMonitor

    tracker = TokenTracker()
    tracker.track("ast_grep", "result text")  # logs if over budget

    monitor = ContextPressureMonitor()
    warning = monitor.check_pressure(
        model="gemini-2.5-pro",
        conversation_history=messages,
    )
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Default budgets (chars approximation — /4 for token estimate) ───────

DEFAULT_BUDGETS: dict[str, int] = {
    "ast_grep": 2000,
    "structural_analysis": 4000,
    "impact_analysis": 3000,
    "semantic_search": 2500,
    "ast_read": 1500,
    "ast_edit": 1000,
    "default": 1000,
}

DEFAULT_CONTEXT_WINDOW = 262144
DEFAULT_COMPRESSION_RATIO = 0.50
DEFAULT_WARNING_RATIO = 0.40
DEFAULT_CHARS_PER_TOKEN = 4.0

# All ast-tools tool names for prefix stripping
AST_TOOLS_TOOL_NAMES = frozenset({
    # Core AST
    "ast_grep", "ast_edit", "ast_read", "ast_generate_stub",
    "ast_refactor_extract_interface", "ast_capsule", "ast_query", "ts_edit",
    # Analysis
    "structural_analysis", "impact_analysis", "module_imports",
    "find_references", "blast_radius_v2", "class_hierarchy",
    "transitive_dependents", "circular_dependencies",
    "dependency_chain", "external_dependencies", "api_surface_diff",
    # Knowledge Graph
    "kg_query", "kg_shortest_path", "kg_neighborhood",
    # Co-change
    "co_change_diff", "co_change_history", "co_change_hotspots",
    "co_change_predict",
    # Dead code / quality
    "dead_code_detection", "dead_code_enhanced", "code_validate_syntax",
    "codebase_summary", "project_info", "repo_skeleton", "file_related_suggest",
    # LSP
    "lsp_available_languages", "lsp_call_hierarchy_in", "lsp_call_hierarchy_out",
    "lsp_check_server", "lsp_definition", "lsp_hover", "lsp_references",
    "lsp_symbols",
    # Index
    "semantic_search", "search_symbols", "find_symbol_definition",
    "list_symbols", "refresh_index", "index_status", "reindex_path",
    "watch_add", "watch_status",
})


def _strip_prefix(tool_name: str) -> str:
    """Strip MCP prefix from tool names for budget lookup."""
    prefixes = ["mcp_ast_tools_tool_", "mcp_ast_tools_"]
    for prefix in prefixes:
        if tool_name.startswith(prefix):
            return tool_name[len(prefix):]
    return tool_name


def _is_ast_tools_tool(tool_name: str) -> bool:
    """Check if a tool name belongs to ast-tools."""
    return _strip_prefix(tool_name) in AST_TOOLS_TOOL_NAMES


class TokenTracker:
    """Tracks token usage and budget adherence for ast-tools tool calls.

    Logs warnings when tool results exceed their configured budget.
    """

    def __init__(self, budgets: dict[str, int] | None = None):
        self.budgets = budgets or dict(DEFAULT_BUDGETS)

    def track(self, tool_name: str, result_text: str) -> dict[str, Any] | None:
        """Track a tool call result against its budget.

        Args:
            tool_name: Name of the tool that was called.
            result_text: The result text to estimate tokens from.

        Returns:
            A dict with budget info if exceeded, None if within budget
            or not an ast-tools tool.
        """
        if not _is_ast_tools_tool(tool_name):
            return None

        raw = _strip_prefix(tool_name)
        budget = self.budgets.get(raw, self.budgets.get("default", 1000))
        estimated = len(result_text) // 4  # rough chars/token

        if estimated > budget:
            logger.warning(
                "ast-tools result exceeded budget: %s ~%dtok (budget: %d)",
                tool_name, estimated, budget,
            )
            return {
                "tool": tool_name,
                "estimated_tokens": estimated,
                "budget": budget,
                "exceeded": True,
            }

        return None


class ContextPressureMonitor:
    """Monitors conversation context pressure and warns when nearing compression.

    Useful as a pre-LLM-call check to avoid hitting context limits.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.context_window = cfg.get("context_window", {})
        self.chars_per_token = (
            cfg.get("token_estimation", {})
            .get("chars_per_token", DEFAULT_CHARS_PER_TOKEN)
        )

    def check_pressure(
        self,
        model: str = "",
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Check if context usage is approaching compression threshold.

        Args:
            model: Model name for per-model context window lookup.
            conversation_history: List of conversation messages with 'content' keys.

        Returns:
            A dict with a warning context block if pressure is high, None otherwise.
        """
        per_model = self.context_window.get("per_model", {})
        context_length = per_model.get(
            model,
            self.context_window.get("default", DEFAULT_CONTEXT_WINDOW),
        )
        threshold_ratio = self.context_window.get(
            "compression_threshold_ratio", DEFAULT_COMPRESSION_RATIO,
        )
        warning_ratio = self.context_window.get(
            "warning_threshold_ratio", DEFAULT_WARNING_RATIO,
        )

        total_chars = sum(
            len(str(m.get("content", "")))
            for m in (conversation_history or [])
        )
        estimated = int(total_chars / self.chars_per_token)
        threshold = int(context_length * threshold_ratio)
        warning_at = int(threshold * (warning_ratio / threshold_ratio))

        if estimated >= warning_at:
            return {
                "context": (
                    f"\n⚠️ **Context Pressure Alert**\n"
                    f"- Usage: ~{estimated:,} tokens "
                    f"({estimated / context_length * 100:.1f}%)\n"
                    f"- Compression at: {threshold:,} tokens "
                    f"({threshold_ratio * 100:.0f}%)\n"
                    f"- Use `/compress` or focus queries.\n"
                ),
            }

        return None

    @staticmethod
    def estimate_tokens(text: str, chars_per_token: float = DEFAULT_CHARS_PER_TOKEN) -> int:
        """Quick token estimate for a text string."""
        return int(len(text) / chars_per_token)
