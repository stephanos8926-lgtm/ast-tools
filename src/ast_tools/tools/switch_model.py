"""MCP tool: Switch the active embedding model.

Usage:
    switch_embedding_model(model_id: str, force: bool = False, auto_reindex: bool = True)

Switches the embedding model used for semantic search. Supports local models
(sentence-transformers), remote inference (RW_InferenceEngine), and API providers
(OpenAI, Gemini, OpenRouter, Cohere).

When switching models, automatically triggers a full reindex if the new model
has a different dimension or if auto_reindex=True.

Available models:
    - bge-small-en-v1.5 (local, 384 dim) - Fast, good quality
    - all-MiniLM-L6-v2 (local, 384 dim) - Very fast, decent quality
    - ms-marco-MiniLM-L-6-v2 (local, 384 dim) - Optimized for retrieval
    - rw-inference-bge (remote, 384 dim) - Remote BGE via RW_InferenceEngine
    - text-embedding-3-small (openai, 1536 dim) - OpenAI small
    - text-embedding-3-large (openai, 3072 dim) - OpenAI large
    - gemini-embedding-001 (gemini, 768 dim) - Google Gemini

Requires:
    - For remote: RW_InferenceEngine running at AST_TOOLS_REMOTE_INFERENCE_URL (default http://localhost:3000)
    - For API providers: Appropriate API keys in environment variables
"""

import json
import logging
from pathlib import Path
from typing import Any

from ast_tools.embeddings.model_registry import EmbeddingModelRegistry

logger = logging.getLogger(__name__)


# Global registry instance
_registry: EmbeddingModelRegistry | None = None


def _get_registry(project_path: str | None = None) -> EmbeddingModelRegistry:
    """Get or create the model registry."""
    global _registry
    if _registry is None:
        root = Path(project_path) if project_path else Path.cwd()
        # Import here to avoid circular imports
        from ast_tools.embeddings.model_registry import EmbeddingModelRegistry
        _registry = EmbeddingModelRegistry(project_root=root)
    return _registry


def _tool_switch_embedding_model(args: dict[str, Any]) -> str:
    """Switch the active embedding model.

    Args:
        model_id: ID of the model to switch to (e.g., 'rw-inference-bge', 'bge-small-en-v1.5')
        force: Force switch even if already active
        auto_reindex: Automatically trigger reindex if model changes (default: True)
        project_path: Optional project root path

    Returns:
        JSON result with switch status and reindex info
    """
    model_id = args.get("model_id", "")
    force = args.get("force", False)
    auto_reindex = args.get("auto_reindex", True)
    project_path = args.get("project_path")

    if not model_id:
        return json.dumps({"error": "model_id is required"}, indent=2)

    try:
        registry = _get_registry(project_path)

        # Run async switch in sync context
        import asyncio

        async def do_switch():
            return await registry.switch_model(model_id, force=force)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(do_switch())

        # If auto_reindex is requested and reindex is needed, trigger it
        if auto_reindex and result.get("reindex_needed"):
            logger.info(f"Auto-triggering reindex for model switch to {model_id}")
            # Import refresh_index tool
            from .refresh_index import _tool_refresh_index

            project_root = Path(project_path) if project_path else Path.cwd()
            refresh_result = _tool_refresh_index({
                "project_path": str(project_root),
                "force": True,
                "embeddings": True,
            })
            try:
                refresh_data = json.loads(refresh_result)
                result["auto_reindex"] = refresh_data
            except json.JSONDecodeError:
                result["auto_reindex_error"] = "Failed to parse reindex result"

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Model switch failed: {e}")
        return json.dumps({"error": str(e), "error_code": "MODEL_SWITCH_FAILED"}, indent=2)


def _tool_list_embedding_models(args: dict[str, Any]) -> str:
    """List all available embedding models.

    Args:
        project_path: Optional project root path

    Returns:
        JSON array of model configurations
    """
    project_path = args.get("project_path")

    try:
        registry = _get_registry(project_path)
        models = registry.list_models()

        result = {
            "current_model": registry.current_model_id,
            "current_config": registry.current_model_config.to_dict() if registry.current_model_config else None,
            "needs_reindex": registry.needs_reindex,
            "available_models": {k: v.to_dict() for k, v in models.items()},
        }

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return json.dumps({"error": str(e), "error_code": "LIST_MODELS_FAILED"}, indent=2)


def _tool_get_embedding_model_info(args: dict[str, Any]) -> str:
    """Get detailed information about the current or a specific embedding model.

    Args:
        model_id: Optional model ID (defaults to current)
        project_path: Optional project root path

    Returns:
        JSON with model configuration and status
    """
    model_id = args.get("model_id")
    project_path = args.get("project_path")

    try:
        registry = _get_registry(project_path)

        if model_id:
            config = registry.get_model(model_id)
            if not config:
                return json.dumps({"error": f"Model not found: {model_id}"}, indent=2)
        else:
            config = registry.current_model_config
            model_id = registry.current_model_id

        result = {
            "model_id": model_id,
            "config": config.to_dict() if config else None,
            "is_current": model_id == registry.current_model_id,
            "needs_reindex": registry.needs_reindex if model_id == registry.current_model_id else None,
        }

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        return json.dumps({"error": str(e), "error_code": "GET_MODEL_INFO_FAILED"}, indent=2)


# Export for MCP server registration
switch_embedding_model_tool = {
    "name": "switch_embedding_model",
    "description": "Switch the active embedding model for semantic search. Supports local, remote, and API providers. Auto-triggers reindex on model change.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "model_id": {
                "type": "string",
                "description": "ID of the model to switch to (e.g., 'rw-inference-bge', 'bge-small-en-v1.5', 'text-embedding-3-small')",
            },
            "force": {
                "type": "boolean",
                "description": "Force switch even if model is already active",
                "default": False,
            },
            "auto_reindex": {
                "type": "boolean",
                "description": "Automatically trigger full reindex if model changes",
                "default": True,
            },
            "project_path": {
                "type": "string",
                "description": "Optional project root path",
            },
        },
        "required": ["model_id"],
    },
}

list_embedding_models_tool = {
    "name": "list_embedding_models",
    "description": "List all available embedding models with their configurations and current status.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Optional project root path",
            },
        },
    },
}

get_embedding_model_info_tool = {
    "name": "get_embedding_model_info",
    "description": "Get detailed information about the current or a specific embedding model.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "model_id": {
                "type": "string",
                "description": "Optional model ID (defaults to current)",
            },
            "project_path": {
                "type": "string",
                "description": "Optional project root path",
            },
        },
    },
}