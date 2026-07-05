"""AST-Tools Token Management Plugin

Tracks token usage for ast-tools and provides context pressure warnings.
Reads token budgets from ~/.ast-tools/config/tokens.yaml (fallback to defaults).
"""

import logging
from functools import partial
from pathlib import Path
from typing import Any

from hermes_cli.plugins import PluginContext

logger = logging.getLogger(__name__)

# ── Default budgets ────────────────────────────────────────────────────

_DEFAULT_BUDGETS: dict[str, int] = {
    "ast_grep": 2000,
    "structural_analysis": 4000,
    "impact_analysis": 3000,
    "semantic_search": 2500,
    "ast_read": 1500,
    "ast_edit": 1000,
    "default": 1000,
}

_DEFAULT_CONTEXT_WINDOW = 262144
_DEFAULT_COMPRESSION_RATIO = 0.50
_DEFAULT_WARNING_RATIO = 0.40
_DEFAULT_CHARS_PER_TOKEN = 4.0

# ── Config loader ──────────────────────────────────────────────────────


def _load_tokens_config() -> dict[str, Any]:
    """Load token budgets from ~/.ast-tools/config/tokens.yaml.

    Falls back to hardcoded defaults if file doesn't exist.
    """
    defaults: dict[str, Any] = {
        "token_budgets": dict(_DEFAULT_BUDGETS),
        "context_window": {
            "default": _DEFAULT_CONTEXT_WINDOW,
            "compression_threshold_ratio": _DEFAULT_COMPRESSION_RATIO,
            "warning_threshold_ratio": _DEFAULT_WARNING_RATIO,
            "per_model": {},
        },
        "token_estimation": {
            "chars_per_token": _DEFAULT_CHARS_PER_TOKEN,
        },
    }

    config_path = Path.home() / ".ast-tools" / "config" / "tokens.yaml"
    if not config_path.exists():
        return defaults

    try:
        import yaml

        raw = yaml.safe_load(config_path.read_text())
        if raw and isinstance(raw, dict):
            merged = dict(defaults)
            for key, val in raw.items():
                if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
                    merged[key].update(val)
                else:
                    merged[key] = val
            return merged
    except Exception as e:
        logger.warning("Failed to load tokens.yaml from %s: %s", config_path, e)

    return defaults


# ── Error correction patterns ──────────────────────────────────────────

_AST_TOOLS_ERROR_CORRECTIONS: dict[str, dict[str, str]] = {
    "ast_edit": {
        "Invalid operation": (
            "**Correct usage:** ast_edit operations:\n"
            "- `rename_function`: {\"function\": \"old_name\", \"new_name\": \"new_name\"}\n"
            "- `replace_node`: {\"pattern\": \"old\", \"replacement\": \"new\"}\n"
            "- `insert_after`: {\"anchor\": \"func\", \"code\": \"new code\"}\n"
            "- `add_parameter`: {\"function\": \"foo\", \"param\": \"bar\", \"type\": \"str\"}\n"
            "Always dry_run=true first!"
        ),
        "dry_run": "⚠️ Always run dry_run=true FIRST to preview changes.",
    },
    "semantic_search": {
        "k exceeds": "⚠️ k=50 is large. Use k=10 + diversity_limit=5 or add lang='python' filter.",
        "no results": "Try broader query or remove kind/lang filters.",
    },
    "ast_grep": {
        "Invalid pattern": "Use $VAR for single node, $$$VAR for multiple. Example: def $FUNC($$$ARGS)",
    },
    "impact_analysis": {
        "symbol not found": "Use find_references first to locate symbol, then impact_analysis on the file.",
    },
}

# ── Plugin registration ────────────────────────────────────────────────


def register(ctx: PluginContext):
    """Register ast-tools token management hooks."""
    cfg = _load_tokens_config()
    ctx.register_hook(
        "post_tool_call",
        partial(_track_ast_tools_usage, budgets=cfg.get("token_budgets", _DEFAULT_BUDGETS)),
    )
    ctx.register_hook(
        "pre_llm_call",
        partial(_check_context_pressure, cfg=cfg),
    )
    ctx.register_hook("post_tool_call", _correct_ast_tools_errors)
    logger.info(
        "ast-tools-tokens plugin registered "
        "(config: %s)",
        "loaded" if Path.home().joinpath(".ast-tools/config/tokens.yaml").exists() else "defaults",
    )


# ── Tool usage tracking ────────────────────────────────────────────────

_AST_TOOLS_TOOL_NAMES = {
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
    "co_change_diff", "co_change_history", "co_change_hotspots", "co_change_predict",
    # Dead code / quality
    "dead_code_detection", "dead_code_enhanced", "code_validate_syntax",
    "codebase_summary", "project_info", "repo_skeleton", "file_related_suggest",
    # LSP
    "lsp_available_languages", "lsp_call_hierarchy_in", "lsp_call_hierarchy_out",
    "lsp_check_server", "lsp_definition", "lsp_hover", "lsp_references", "lsp_symbols",
    # Index
    "semantic_search", "search_symbols", "find_symbol_definition", "list_symbols",
    "refresh_index", "index_status", "reindex_path",
    "watch_add", "watch_status",
}


def _is_ast_tools_tool(tool_name: str) -> bool:
    """Check if a tool name belongs to ast-tools (supports both bare and MCP-prefixed names)."""
    if tool_name.startswith("mcp_ast_tools_tool_"):
        return tool_name[len("mcp_ast_tools_tool_"):] in _AST_TOOLS_TOOL_NAMES
    return tool_name in _AST_TOOLS_TOOL_NAMES


def _track_ast_tools_usage(tool_name: str, params: dict, result: str, budgets: dict[str, int], **kwargs):
    """Log token usage when ast-tools tools return large results."""
    if not _is_ast_tools_tool(tool_name):
        return
    # Strip prefix for budget lookup
    raw_name = tool_name
    if raw_name.startswith("mcp_ast_tools_tool_"):
        raw_name = raw_name[len("mcp_ast_tools_tool_"):]
    budget = budgets.get(raw_name, budgets.get("default", 1000))
    estimated = len(result) // 4
    if estimated > budget:
        logger.warning(
            "ast-tools result exceeded budget: %s ~%dtok (budget: %d)",
            tool_name, estimated, budget,
        )


# ── Context pressure ───────────────────────────────────────────────────


def _check_context_pressure(
    session_id: str,
    user_message: str,
    conversation_history: list,
    is_first_turn: bool,
    model: str,
    cfg: dict[str, Any],
    **kwargs,
) -> dict | None:
    """Warn when context usage approaches compression threshold."""
    cw = cfg.get("context_window", {})
    per_model = cw.get("per_model", {})
    context_length = per_model.get(model, cw.get("default", _DEFAULT_CONTEXT_WINDOW))
    threshold_ratio = cw.get("compression_threshold_ratio", _DEFAULT_COMPRESSION_RATIO)
    warning_ratio = cw.get("warning_threshold_ratio", _DEFAULT_WARNING_RATIO)
    chars_per_token = cfg.get("token_estimation", {}).get("chars_per_token", _DEFAULT_CHARS_PER_TOKEN)

    total_chars = sum(len(str(m.get("content", ""))) for m in conversation_history)
    estimated = int(total_chars / chars_per_token)
    threshold = int(context_length * threshold_ratio)
    warning_at = int(threshold * (warning_ratio / threshold_ratio))

    if estimated >= warning_at:
        return {
            "context": (
                f"\n⚠️ **Context Pressure Alert**\n"
                f"- Usage: ~{estimated:,} tokens ({estimated / context_length * 100:.1f}%)\n"
                f"- Compression at: {threshold:,} tokens ({threshold_ratio * 100:.0f}%)\n"
                f"- Use `/compress` or focus queries.\n"
            ),
        }
    return None


# ── Error correction ───────────────────────────────────────────────────


def _correct_ast_tools_errors(tool_name: str, params: dict, result: str, **kwargs):
    """Intercept failed ast-tools calls and inject usage guidance."""
    if not _is_ast_tools_tool(tool_name):
        return None
    # Strip prefix for correction lookup
    raw_name = tool_name
    if raw_name.startswith("mcp_ast_tools_tool_"):
        raw_name = raw_name[len("mcp_ast_tools_tool_"):]
    if "Error:" in str(result) or "error" in str(result).lower()[:50]:
        corrections = _AST_TOOLS_ERROR_CORRECTIONS.get(raw_name, {})
        for pattern, correction in corrections.items():
            if pattern.lower() in str(result).lower():
                return {"context": f"\n⚠️ **AST-Tools Usage Correction:**\n{correction}\n"}
        if raw_name in _AST_TOOLS_ERROR_CORRECTIONS:
            return {"context": f"\n⚠️ **AST-Tools Usage:** Check docs for {raw_name}.\n"}
    return None