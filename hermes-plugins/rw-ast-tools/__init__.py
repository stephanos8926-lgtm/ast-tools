"""rw-ast-tools — Unified Hermes plugin for AST-tools integration.

Thin shim around ast_tools.agent_integration modules.
All logic lives in the rw-ast-tools package itself.

Replaces: ast-tools-context, ast-tools-tokens, ast-tools-codebase-index
"""

from __future__ import annotations

import logging
from functools import partial
from pathlib import Path
from typing import Any

from hermes_cli.plugins import PluginContext

logger = logging.getLogger(__name__)

# ── Agent Integration Modules ───────────────────────────────────────────

from ast_tools.agent_integration import (
    build_ast_tools_context,
    detect_ast_query,
    correct_tool_error,
)
from ast_tools.agent_integration.token_tracker import (
    TokenTracker,
    ContextPressureMonitor,
)

_TRACKER = TokenTracker()
_PRESSURE_MONITOR = ContextPressureMonitor()


# ── Hook: pre_llm_call — Context injection ──────────────────────────────


def _on_pre_llm_call(
    session_id: str,
    user_message: str,
    conversation_history: list,
    is_first_turn: bool,
    model: str,
    **kwargs,
) -> dict | None:
    """Inject AST-tools context when user asks about code analysis."""
    # Detect if query relates to AST tools
    if not detect_ast_query(user_message):
        return None

    context = build_ast_tools_context(user_message)
    if context:
        return {"context": context}
    return None


# ── Hook: on_session_start — Quick index ────────────────────────────────


def _on_session_start(session_id: str, **kwargs) -> dict:
    """Inject compact AST-tools reference at session start."""
    return {
        "context": (
            "## AST-Tools Quick Index\n\n"
            "**Core:** `ast_grep` (structural search), `ast_read` (API surface), "
            "`ast_edit` (surgical edits — dry_run FIRST!), "
            "`semantic_search` (inject_context=True)\n\n"
            "**Analysis:** `impact_analysis` (before API changes), "
            "`module_imports` (before splits), `circular_dependencies`, "
            "`class_hierarchy`, `transitive_dependents`\n\n"
            "**Gotchas:** `ast_edit`: Always dry_run=true first | "
            "`semantic_search`: inject_context=True (default), "
            "token_budget=4096, diversity_limit=3 | "
            "`refresh_index`: incremental via SHA256\n"
        ),
    }


# ── Hook: post_tool_call — Token tracking + error correction ────────────


_AST_TOOLS_TOOL_NAMES = frozenset({
    "ast_grep", "ast_edit", "ast_read", "ast_generate_stub",
    "ast_refactor_extract_interface", "ast_capsule", "ast_query", "ts_edit",
    "structural_analysis", "impact_analysis", "module_imports",
    "find_references", "blast_radius_v2", "class_hierarchy",
    "transitive_dependents", "circular_dependencies",
    "dependency_chain", "external_dependencies", "api_surface_diff",
    "kg_query", "kg_shortest_path", "kg_neighborhood",
    "co_change_diff", "co_change_history", "co_change_hotspots", "co_change_predict",
    "dead_code_detection", "dead_code_enhanced", "code_validate_syntax",
    "codebase_summary", "project_info", "repo_skeleton", "file_related_suggest",
    "lsp_available_languages", "lsp_call_hierarchy_in", "lsp_call_hierarchy_out",
    "lsp_check_server", "lsp_definition", "lsp_hover", "lsp_references", "lsp_symbols",
    "semantic_search", "search_symbols", "find_symbol_definition", "list_symbols",
    "refresh_index", "index_status", "reindex_path",
    "watch_add", "watch_status",
    # New metadata tools
    "context_inject", "context_status", "token_status", "validate_usage",
})


def _is_ast_tools_tool(tool_name: str) -> bool:
    if tool_name.startswith("mcp_ast_tools_tool_"):
        return tool_name[len("mcp_ast_tools_tool_"):] in _AST_TOOLS_TOOL_NAMES
    if tool_name.startswith("mcp_ast_tools_"):
        return tool_name[len("mcp_ast_tools_"):] in _AST_TOOLS_TOOL_NAMES
    return tool_name in _AST_TOOLS_TOOL_NAMES


def _on_post_tool_call(
    tool_name: str,
    params: dict,
    result: str,
    **kwargs,
) -> dict | None:
    """Track token usage and check for common errors."""
    if not _is_ast_tools_tool(tool_name):
        return None

    # 1. Token tracking
    _TRACKER.track(tool_name, str(result) if result else "")

    # 2. Error correction
    correction = correct_tool_error(tool_name, str(result) if result else "")
    if correction:
        return correction

    return None


# ── Registration ────────────────────────────────────────────────────────


def register(ctx: PluginContext):
    """Register rw-ast-tools hooks."""
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    logger.info(
        "rw-ast-tools plugin v1.0.0 registered — "
        "4 hooks (pre_llm_call, post_tool_call, on_session_start, on_session_end)"
    )