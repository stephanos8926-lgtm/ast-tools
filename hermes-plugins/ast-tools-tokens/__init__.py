"""AST-Tools Token Management Plugin

Tracks token usage for ast-tools and provides compression-aware context injection.
Now reads token budgets from ~/.ast-tools/config/tokens.yaml.
"""

import json
import logging
import os
from functools import partial
from pathlib import Path
from typing import Any

from hermes_cli.plugins import PluginContext

logger = logging.getLogger(__name__)

# ── Default budgets (fallback when no config file) ──────────────────────

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
    config_path = Path.home() / ".ast-tools" / "config" / "tokens.yaml"

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

    if not config_path.exists():
        return defaults

    try:
        import yaml
        raw = yaml.safe_load(config_path.read_text())
        if raw and isinstance(raw, dict):
            # Merge: raw values override defaults
            merged = dict(defaults)
            for key, val in raw.items():
                if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
                    merged[key].update(val)
                else:
                    merged[key] = val
            return merged
    except Exception as e:
        logger.warning(f"Failed to load tokens.yaml from {config_path}: {e}")

    return defaults


# ── Error correction patterns ───────────────────────────────────────────

_AST_TOOLS_ERROR_CORRECTIONS: dict[str, dict[str, str]] = {
    "ast_edit": {
        "Invalid operation": (
            "**Correct usage:** ast_edit operations are specific:\n"
            "- `rename_function`: {\"function\": \"old_name\", \"new_name\": \"new_name\"}\n"
            "- `replace_node`: {\"pattern\": \"old\", \"replacement\": \"new\"}\n"
            "- `insert_after`: {\"anchor\": \"func\", \"code\": \"new code\"}\n"
            "- `add_parameter`: {\"function\": \"foo\", \"param\": \"bar\", \"type\": \"str\"}\n"
            "Always dry_run=true first!"
        ),
        "dry_run": "⚠️ Always run dry_run=true FIRST to preview changes. Then re-run with dry_run=false.",
    },
    "semantic_search": {
        "k exceeds": "⚠️ k=50 is large. Use k=10 + diversity_limit=5 for broad results, or add lang='python' filter.",
        "no results": "Try broader query or remove kind/lang filters. FTS5 needs keyword matches for recall.",
    },
    "ast_grep": {
        "Invalid pattern": "Use $VAR for single node, $$$VAR for multiple nodes. Example: def $FUNC($$$ARGS)",
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
        f"(config: {'loaded' if Path.home().joinpath('.ast-tools/config/tokens.yaml').exists() else 'defaults'})"
    )


# ── Tool usage tracking ────────────────────────────────────────────────


def _track_ast_tools_usage(tool_name: str, params: dict, result: str, budgets: dict[str, int], **kwargs):
    if not tool_name.startswith("mcp_ast_tools_"):
        return
    tool_key = tool_name.replace("mcp_ast_tools_", "").split("_")[0]
    budget = budgets.get(tool_key, budgets.get("default", 1000))
    estimated = len(result) // 4
    if estimated > budget:
        logger.warning(
            f"ast-tools result exceeded budget: {tool_name} ~{estimated}tok "
            f"(budget: {budget})"
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
                f"- Usage: ~{estimated:,} tokens ({estimated/context_length*100:.1f}%)\n"
                f"- Compression at: {threshold:,} tokens ({threshold_ratio*100:.0f}%)\n"
                f"- Use `/compress` or focus queries.\n"
            )
        }
    return None


# ── Error correction ───────────────────────────────────────────────────


def _correct_ast_tools_errors(tool_name: str, params: dict, result: str, **kwargs):
    if not tool_name.startswith("mcp_ast_tools_"):
        return
    tool_key = tool_name.replace("mcp_ast_tools_", "")
    if "Error:" in str(result) or "error" in str(result).lower()[:50]:
        corrections = _AST_TOOLS_ERROR_CORRECTIONS.get(tool_key, {})
        for pattern, correction in corrections.items():
            if pattern.lower() in str(result).lower():
                return {"context": f"\n⚠️ **AST-Tools Usage Correction:**\n{correction}\n"}
        if tool_key in _AST_TOOLS_ERROR_CORRECTIONS:
            return {"context": f"\n⚠️ **AST-Tools Usage:** Check docs for {tool_key}.\n"}
    return None