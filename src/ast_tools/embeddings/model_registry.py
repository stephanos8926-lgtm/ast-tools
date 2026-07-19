"""Embedding model registry with dynamic switching and auto-reindexing.

Tracks the active embedding model and automatically rebuilds the index
when the model changes, supporting local, remote, and API-based providers.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ast_tools.config.unified import RUNTIME

from .provider import EmbeddingBackend, EmbeddingProvider, RemoteInferenceConfig

logger = logging.getLogger(__name__)


class EmbeddingModelProvider(Enum):
    """Supported embedding model providers."""

    LOCAL = "local"  # sentence-transformers
    REMOTE = "remote"  # RW_InferenceEngine
    GEMINI = "gemini"  # Google Generative AI
    OPENROUTER = "openrouter"  # OpenRouter API
    OPENAI = "openai"  # OpenAI API
    COHERE = "cohere"  # Cohere API


@dataclass
class EmbeddingModelConfig:
    """Configuration for an embedding model."""

    provider: EmbeddingModelProvider
    model_name: str
    dimension: int
    # Provider-specific config
    local_cache_dir: str | None = None
    remote_config: RemoteInferenceConfig | None = None
    api_key: str | None = None
    api_base_url: str | None = None
    # Metadata
    description: str = ""
    max_batch_size: int = 32

    @property
    def unique_id(self) -> str:
        """Generate unique identifier for this model configuration."""
        content = f"{self.provider.value}:{self.model_name}:{self.dimension}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.value,
            "model_name": self.model_name,
            "dimension": self.dimension,
            "local_cache_dir": self.local_cache_dir,
            "remote_config": {
                "base_url": self.remote_config.base_url if self.remote_config else None,
            } if self.remote_config else None,
            "api_base_url": self.api_base_url,
            "description": self.description,
            "max_batch_size": self.max_batch_size,
            "unique_id": self.unique_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmbeddingModelConfig:
        remote_config = None
        if data.get("remote_config") and data["remote_config"].get("base_url"):
            remote_config = RemoteInferenceConfig(base_url=data["remote_config"]["base_url"])
        return cls(
            provider=EmbeddingModelProvider(data["provider"]),
            model_name=data["model_name"],
            dimension=data["dimension"],
            local_cache_dir=data.get("local_cache_dir"),
            remote_config=remote_config,
            api_key=data.get("api_key"),
            api_base_url=data.get("api_base_url"),
            description=data.get("description", ""),
            max_batch_size=data.get("max_batch_size", 32),
        )


# Default model configurations — batch sizes sourced from RUNTIME
DEFAULT_MODELS = {
    "bge-small-en-v1.5": EmbeddingModelConfig(
        provider=EmbeddingModelProvider.LOCAL,
        model_name="bge-small-en-v1.5",
        dimension=384,
        description="BGE small English v1.5 - fast, good quality",
        max_batch_size=RUNTIME.batch_size_embeddings_large,
    ),
    "all-MiniLM-L6-v2": EmbeddingModelConfig(
        provider=EmbeddingModelProvider.LOCAL,
        model_name="all-MiniLM-L6-v2",
        dimension=384,
        description="MiniLM L6 v2 - very fast, decent quality",
        max_batch_size=RUNTIME.batch_size_embeddings_large,
    ),
    "ms-marco-MiniLM-L-6-v2": EmbeddingModelConfig(
        provider=EmbeddingModelProvider.LOCAL,
        model_name="ms-marco-MiniLM-L-6-v2",
        dimension=384,
        description="MS MARCO MiniLM - optimized for retrieval",
        max_batch_size=RUNTIME.batch_size_embeddings_large,
    ),
    "rw-inference-bge": EmbeddingModelConfig(
        provider=EmbeddingModelProvider.REMOTE,
        model_name="bge-small-en-v1.5",
        dimension=384,
        description="Remote BGE via RW_InferenceEngine",
        max_batch_size=RUNTIME.batch_size_embeddings_standard,
    ),
    "text-embedding-3-small": EmbeddingModelConfig(
        provider=EmbeddingModelProvider.OPENAI,
        model_name="text-embedding-3-small",
        dimension=1536,
        description="OpenAI text-embedding-3-small",
        max_batch_size=RUNTIME.batch_size_embeddings_api,
    ),
    "text-embedding-3-large": EmbeddingModelConfig(
        provider=EmbeddingModelProvider.OPENAI,
        model_name="text-embedding-3-large",
        dimension=3072,
        description="OpenAI text-embedding-3-large",
        max_batch_size=RUNTIME.batch_size_embeddings_api,
    ),
    "gemini-embedding-001": EmbeddingModelConfig(
        provider=EmbeddingModelProvider.GEMINI,
        model_name="gemini-embedding-001",
        dimension=768,
        description="Google Gemini Embedding 001",
        max_batch_size=100,
    ),
}


@dataclass
class ModelRegistryState:
    """Persisted state of the model registry."""

    current_model_id: str
    current_model_config: dict[str, Any]
    last_switched: float
    index_built_for_model: str  # model unique_id that index was built with
    pending_reindex: bool = False

    def to_file(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "current_model_id": self.current_model_id,
            "current_model_config": self.current_model_config,
            "last_switched": self.last_switched,
            "index_built_for_model": self.index_built_for_model,
            "pending_reindex": self.pending_reindex,
        }, indent=2))

    @classmethod
    def from_file(cls, path: Path) -> ModelRegistryState | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return cls(**data)
        except Exception:
            return None


class EmbeddingModelRegistry:
    """Registry for managing embedding models with auto-switching and reindexing."""

    def __init__(
        self,
        project_root: Path,
        available_models: dict[str, EmbeddingModelConfig] | None = None,
        default_model: str = "bge-small-en-v1.5",
        reindex_callback: Callable[[], Any] | None = None,
    ):
        self.project_root = Path(project_root)
        self.available_models = available_models or DEFAULT_MODELS
        self.default_model = default_model
        self.reindex_callback = reindex_callback

        # State file location
        self.state_dir = self.project_root / ".ast-tools" / "models"
        self.state_file = self.state_dir / "model_registry.json"

        # Current state
        self._state: ModelRegistryState | None = None
        self._current_provider: EmbeddingProvider | None = None
        self._provider_lock = asyncio.Lock()

        # Load persisted state
        self._load_state()

    def _load_state(self) -> None:
        """Load registry state from disk."""
        self._state = ModelRegistryState.from_file(self.state_file)

        if self._state is None:
            # First run - initialize with default model
            default_config = self.available_models.get(self.default_model)
            if default_config:
                self._state = ModelRegistryState(
                    current_model_id=self.default_model,
                    current_model_config=default_config.to_dict(),
                    last_switched=time.time(),
                    index_built_for_model=default_config.unique_id,
                    pending_reindex=False,
                )
                self._save_state()
            else:
                raise ValueError(f"Default model {self.default_model} not found in available models")

    def _save_state(self) -> None:
        """Persist registry state to disk."""
        if self._state:
            self._state.to_file(self.state_file)

    @property
    def current_model_id(self) -> str:
        return self._state.current_model_id if self._state else self.default_model

    @property
    def current_model_config(self) -> EmbeddingModelConfig:
        return EmbeddingModelConfig.from_dict(self._state.current_model_config) if self._state else None

    @property
    def needs_reindex(self) -> bool:
        """Check if index needs to be rebuilt due to model change."""
        if not self._state:
            return True
        current_config = self.current_model_config
        if not current_config:
            return True
        return self._state.index_built_for_model != current_config.unique_id or self._state.pending_reindex

    def list_models(self) -> dict[str, EmbeddingModelConfig]:
        """Get all available model configurations."""
        return self.available_models.copy()

    def get_model(self, model_id: str) -> EmbeddingModelConfig | None:
        """Get model configuration by ID."""
        return self.available_models.get(model_id)

    async def switch_model(self, model_id: str, force: bool = False) -> dict[str, Any]:
        """Switch to a different embedding model.

        Args:
            model_id: ID of the model to switch to
            force: If True, skip confirmation and switch even if already active

        Returns:
            Status dict with switch result and reindex info
        """
        if model_id not in self.available_models:
            return {"success": False, "error": f"Unknown model: {model_id}"}

        target_config = self.available_models[model_id]

        if not force and model_id == self.current_model_id:
            return {
                "success": True,
                "message": f"Already using model: {model_id}",
                "model": model_id,
                "reindex_needed": self.needs_reindex,
            }

        # Check if index needs rebuild
        reindex_needed = target_config.unique_id != (self._state.index_built_for_model if self._state else "")

        # Update state
        old_model_id = self.current_model_id
        self._state.current_model_id = model_id
        self._state.current_model_config = target_config.to_dict()
        self._state.last_switched = time.time()
        self._state.pending_reindex = reindex_needed
        self._save_state()

        # Invalidate current provider to force reload
        async with self._provider_lock:
            if self._current_provider:
                await self._current_provider.close()
                self._current_provider = None

        result = {
            "success": True,
            "message": f"Switched from {old_model_id} to {model_id}",
            "old_model": old_model_id,
            "new_model": model_id,
            "reindex_needed": reindex_needed,
            "model_config": target_config.to_dict(),
        }

        # Trigger reindex if callback provided
        if reindex_needed and self.reindex_callback:
            try:
                logger.info(f"Auto-triggering reindex for model switch to {model_id}")
                await self.reindex_callback()
                # Mark reindex complete
                self._state.index_built_for_model = target_config.unique_id
                self._state.pending_reindex = False
                self._save_state()
                result["reindex_triggered"] = True
            except Exception as e:
                logger.error(f"Auto-reindex failed: {e}")
                result["reindex_error"] = str(e)

        return result

    async def get_provider(self) -> EmbeddingProvider:
        """Get or create the embedding provider for the current model."""
        async with self._provider_lock:
            if self._current_provider is not None:
                return self._current_provider

            config = self.current_model_config
            if not config:
                raise RuntimeError("No model configured")

            # Create provider based on model config
            if config.provider == EmbeddingModelProvider.LOCAL:
                provider = EmbeddingProvider(backend=EmbeddingBackend.LOCAL)
            elif config.provider == EmbeddingModelProvider.REMOTE:
                remote_config = config.remote_config or RemoteInferenceConfig.from_env()
                provider = EmbeddingProvider(backend=EmbeddingBackend.REMOTE, remote_config=remote_config)
            else:
                # For API providers, we'd need to implement specific clients
                # For now, fall back to local
                logger.warning(f"Provider {config.provider.value} not fully implemented, falling back to local")
                provider = EmbeddingProvider(backend=EmbeddingBackend.LOCAL)

            self._current_provider = provider
            return provider

    async def close(self) -> None:
        """Close the current provider."""
        async with self._provider_lock:
            if self._current_provider:
                await self._current_provider.close()
                self._current_provider = None


# Global registry instance (lazy-initialized)
_global_registry: EmbeddingModelRegistry | None = None


def get_model_registry(
    project_root: Path | None = None,
    available_models: dict[str, EmbeddingModelConfig] | None = None,
    default_model: str = "bge-small-en-v1.5",
    reindex_callback: Callable[[], Any] | None = None,
) -> EmbeddingModelRegistry:
    """Get or create the global model registry."""
    global _global_registry
    if _global_registry is None:
        if project_root is None:
            project_root = Path.cwd()
        _global_registry = EmbeddingModelRegistry(
            project_root=project_root,
            available_models=available_models,
            default_model=default_model,
            reindex_callback=reindex_callback,
        )
    return _global_registry


async def close_model_registry() -> None:
    """Close the global model registry."""
    global _global_registry
    if _global_registry is not None:
        await _global_registry.close()
        _global_registry = None
