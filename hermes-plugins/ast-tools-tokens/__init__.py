"""
AST-Tools Token Management Plugin

Tracks token usage for ast-tools and provides compression-aware context injection.
"""

from hermes_cli.plugins import PluginContext
import logging

logger = logging.getLogger(__name__)

# Token budgets for ast-tools results (rough estimates, 4 chars ≈ 1 token)
AST_TOOLS_TOKEN_BUDGETS = {
    "ast_grep": 2000,
    "structural_analysis": 4000,
    "impact_analysis": 3000,
    "semantic_search": 2500,
    "ast_read": 1500,
    "ast_edit": 1000,
    "default": 1000
}


def register(ctx: PluginContext):
    """Register ast-tools token management hooks."""
    ctx.register_hook("post_tool_call", track_ast_tools_usage)
    ctx.register_hook("pre_llm_call", check_context_pressure)


def track_ast_tools_usage(tool_name: str, params: dict, result: str, **kwargs):
    """
    Track token usage for ast-tools to detect verbose results.
    
    Logs warnings when results exceed token budgets.
    """
    if not tool_name.startswith("mcp_ast_tools_"):
        return
    
    # Extract tool type
    tool_key = tool_name.replace("mcp_ast_tools_", "").split("_")[0]
    budget = AST_TOOLS_TOKEN_BUDGETS.get(tool_key, AST_TOOLS_TOKEN_BUDGETS["default"])
    
    # Estimate tokens (4 chars per token is rough average)
    result_chars = len(result)
    estimated_tokens = result_chars // 4
    
    if estimated_tokens > budget:
        logger.warning(
            f"ast-tools result exceeded budget: {tool_name} used ~{estimated_tokens} tokens "
            f"(budget: {budget}). Consider using limit parameters or result filtering."
        )
        
        # Could add: Store truncated version in session memory for reference
        # session = get_session(kwargs.get('session_id', ''))
        # session.store_truncated_result(tool_name, result, budget)


def check_context_pressure(
    session_id: str,
    user_message: str,
    conversation_history: list,
    is_first_turn: bool,
    model: str,
    **kwargs
) -> dict | None:
    """
    Check context pressure and warn when approaching compression threshold.
    
    Injects context warning when usage is high.
    """
    # Rough token estimation
    total_chars = 0
    for msg in conversation_history:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
    
    estimated_tokens = total_chars // 4
    
    # Get model context length
    context_lengths = {
        "qwen/qwen3.5-397b-a17b": 262144,
        "default": 262144
    }
    context_length = context_lengths.get(model, 262144)
    
    # Compression threshold (50% default)
    compression_threshold = int(context_length * 0.50)
    
    # Calculate usage percentage
    usage_pct = (estimated_tokens / context_length) * 100
    threshold_pct = (estimated_tokens / compression_threshold * 100) if compression_threshold > 0 else 0
    
    # Warn when approaching compression (80% of threshold = 40% of total)
    if estimated_tokens >= compression_threshold * 0.80:
        return {
            "context": f"""

⚠️ **Context Pressure Alert**

- Current usage: ~{estimated_tokens:,} tokens ({usage_pct:.1f}% of window)
- Compression threshold: {compression_threshold:,} tokens (50%)
- Compression will fire soon if usage continues

**Recommendations:**
- Use `/compress` for manual compression with focus topic
- Focus queries on recent context
- For large codebases, use semantic_search with focused queries instead of full context injection
"""
        }
    
    return None