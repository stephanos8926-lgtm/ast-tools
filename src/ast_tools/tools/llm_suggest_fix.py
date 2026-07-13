"""MCP tool handler for LLM-assisted fix suggestion."""

from __future__ import annotations

from typing import Any

from ast_tools.config.unified import load_unified_config
from ast_tools.llm.client import LLMClient, LLMFixContext


def _tool_llm_suggest_fix(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Suggest a fix for a code issue using a configured LLM.

    Uses configured LLM backends (local or remote) to suggest a fix
    for a given code snippet with diagnostic context. Falls back
    through the provider chain if the primary backend fails.

    Args:
        code: Source code snippet to fix
        diagnostic: Human-readable diagnostic message
        diagnostic_code: Rule code (e.g., "F401", "E302")
        file_path: Path to the file (for context)
        language: Programming language (python, typescript, etc.)
        context_lines: Lines of context to include (default: 20)

    Returns:
        Fix result with diff, confidence, model info, and token usage
    """
    import asyncio

    code = params.get("code", "")
    diagnostic = params.get("diagnostic", "")
    diagnostic_code = params.get("diagnostic_code", "")
    file_path = params.get("file_path", "unknown")
    language = params.get("language", "python")
    context_lines = params.get("context_lines", 20)

    if not code:
        return {"error": "code is required", "error_code": "INVALID_PARAMS"}
    if not diagnostic:
        return {"error": "diagnostic is required", "error_code": "INVALID_PARAMS"}

    # Load config (from workspace or defaults)
    config = load_unified_config()
    llm_config = config.lsp.llm

    if not llm_config.enabled:
        return {
            "error": "LLM is disabled in config (lsp.llm.enabled)",
            "error_code": "DISABLED",
        }

    # Build fix context
    fix_context = LLMFixContext(
        code=code,
        diagnostic_message=diagnostic,
        diagnostic_code=diagnostic_code,
        file_path=file_path,
        language=language,
        context_lines=context_lines,
    )

    # Create client and run
    client = LLMClient(llm_config)
    try:
        result = asyncio.run(client.suggest_fix(fix_context))
    finally:
        asyncio.run(client.close())

    if not result.success:
        return {
            "success": False,
            "error": result.error,
            "error_code": "BACKEND_FAILED",
            "model_used": result.model_used,
        }

    return {
        "success": True,
        "diff": result.diff,
        "confidence": result.confidence,
        "model_used": result.model_used,
        "provider": result.provider,
        "token_usage": result.token_usage,
    }


def _tool_llm_check_available(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Check if any LLM backend is available.

    Tests connectivity to configured backends. For local backends,
    performs a real HTTP health check. For remote backends, checks
    if the required API key environment variable is set.

    Returns:
        Availability status with backend info
    """
    import asyncio

    config = load_unified_config()
    llm_config = config.lsp.llm

    client = LLMClient(llm_config)
    try:
        available = asyncio.run(client.is_available())
    finally:
        asyncio.run(client.close())

    return {
        "available": available,
        "enabled": llm_config.enabled,
        "prefer_local": llm_config.prefer_local,
        "local_backend": llm_config.local_backend if llm_config.prefer_local else None,
        "remote_provider": llm_config.remote_provider,
        "remote_model": llm_config.remote_model,
        "remote_fallback_chain": llm_config.remote_fallback_chain,
    }
