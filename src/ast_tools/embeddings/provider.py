"""Unified embedding provider supporting local and remote backends.

Provides a single interface for generating embeddings regardless of whether
the backend is local (sentence-transformers) or remote (RW_InferenceEngine).
Automatically handles backend selection and fallback.
"""

from __future__ import annotations

import asyncio
import logging
import os
from enum import Enum
from typing import Any

from ast_tools.config.unified import RUNTIME

from .model import generate_batch_embeddings, generate_embedding
from .remote_inference import RemoteInferenceClient, RemoteInferenceConfig

logger = logging.getLogger(__name__)


class EmbeddingBackend(Enum):
    """Available embedding backends."""

    LOCAL = "local"
    REMOTE = "remote"
    AUTO = "auto"  # Try remote first, fallback to local


class EmbeddingProvider:
    """Unified embedding provider supporting multiple backends."""

    def __init__(
        self,
        backend: EmbeddingBackend = EmbeddingBackend.AUTO,
        remote_config: RemoteInferenceConfig | None = None,
    ):
        self.backend = backend
        self._remote_config = remote_config or RemoteInferenceConfig.from_env()
        self._remote_client: RemoteInferenceClient | None = None
        self._local_available = False
        self._remote_available = False

    async def _ensure_remote_client(self) -> RemoteInferenceClient | None:
        """Get or create remote client and verify health."""
        if self._remote_client is None:
            self._remote_client = RemoteInferenceClient(self._remote_config)

        if self._remote_client:
            self._remote_available = await self._remote_client.health_check()
            if not self._remote_available:
                logger.warning("Remote inference engine health check failed")
                return None
        return self._remote_client

    def _check_local_available(self) -> bool:
        """Check if local embedding model is available."""
        if self._local_available:
            return True
        try:
            # Just check if we can import - don't load model yet
            import sentence_transformers  # noqa: F401
            self._local_available = True
            return True
        except ImportError:
            self._local_available = False
            return False

    async def _select_backend(self) -> EmbeddingBackend:
        """Select the best available backend based on configuration."""
        if self.backend == EmbeddingBackend.LOCAL:
            if self._check_local_available():
                return EmbeddingBackend.LOCAL
            logger.warning("Local backend requested but not available")
            return EmbeddingBackend.REMOTE

        if self.backend == EmbeddingBackend.REMOTE:
            client = await self._ensure_remote_client()
            if client and self._remote_available:
                return EmbeddingBackend.REMOTE
            logger.warning("Remote backend requested but not available")
            if self._check_local_available():
                logger.info("Falling back to local backend")
                return EmbeddingBackend.LOCAL
            raise RuntimeError("No embedding backend available")

        # AUTO mode: try remote first, fallback to local
        client = await self._ensure_remote_client()
        if client and self._remote_available:
            return EmbeddingBackend.REMOTE

        if self._check_local_available():
            logger.info("Remote backend unavailable, using local backend")
            return EmbeddingBackend.LOCAL

        raise RuntimeError(
            "No embedding backend available. "
            "Install sentence-transformers for local or run RW_InferenceEngine for remote."
        )

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text using the best available backend."""
        if not text or not text.strip():
            return [0.0] * RUNTIME.embedding_dim

        backend = await self._select_backend()

        if backend == EmbeddingBackend.REMOTE:
            try:
                return await self._remote_client.embed(text)
            except Exception as e:
                logger.warning(f"Remote embedding failed, falling back to local: {e}")
                if self._check_local_available():
                    return generate_embedding(text)
                raise

        # Local backend
        return generate_embedding(text)

    async def generate_batch_embeddings(
        self,
        texts: list[str],
        batch_size: int = 16,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        backend = await self._select_backend()

        if backend == EmbeddingBackend.REMOTE:
            try:
                return await self._remote_client.embed_batch(texts)
            except Exception as e:
                logger.warning(f"Remote batch embedding failed, falling back to local: {e}")
                if self._check_local_available():
                    return generate_batch_embeddings(texts, batch_size=batch_size)
                raise

        # Local backend
        return generate_batch_embeddings(texts, batch_size=batch_size)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[float]:
        """Rerank documents by relevance to query.

        Note: Currently only available with remote backend.
        """
        if not documents:
            return []

        if self.backend == EmbeddingBackend.LOCAL:
            logger.warning("Reranking not available with local backend")
            # Return dummy scores for local
            return [1.0 / (i + 1) for i in range(len(documents))]

        client = await self._ensure_remote_client()
        if client and self._remote_available:
            try:
                return await client.rerank(query, documents, top_k=top_k)
            except Exception as e:
                logger.error(f"Remote reranking failed: {e}")
                raise

        raise RuntimeError("No reranking backend available")

    async def close(self) -> None:
        """Close any open connections."""
        if self._remote_client:
            await self._remote_client.close()
            self._remote_client = None
            self._remote_available = False


# Global provider instance (lazy-initialized)
_global_provider: EmbeddingProvider | None = None


def get_embedding_provider(
    backend: EmbeddingBackend | None = None,
    remote_config: RemoteInferenceConfig | None = None,
) -> EmbeddingProvider:
    """Get or create the global embedding provider."""
    global _global_provider
    if _global_provider is None:
        be = backend or EmbeddingBackend(
            os.environ.get("AST_TOOLS_EMBEDDING_BACKEND", "auto").lower()
        )
        _global_provider = EmbeddingProvider(backend=be, remote_config=remote_config)
    return _global_provider


async def close_embedding_provider() -> None:
    """Close the global embedding provider."""
    global _global_provider
    if _global_provider is not None:
        await _global_provider.close()
        _global_provider = None


# Convenience functions that use the global provider
async def provider_generate_embedding(text: str) -> list[float]:
    """Generate embedding using the global provider."""
    provider = get_embedding_provider()
    return await provider.generate_embedding(text)


async def provider_generate_batch_embeddings(
    texts: list[str],
    batch_size: int = 16,
) -> list[list[float]]:
    """Generate batch embeddings using the global provider."""
    provider = get_embedding_provider()
    return await provider.generate_batch_embeddings(texts, batch_size=batch_size)


async def provider_rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int | None = None,
) -> list[float]:
    """Rerank candidates using the global provider."""
    provider = get_embedding_provider()
    # Extract content from candidates for reranking
    documents = [c.get("content", c.get("text", c.get("docstring", ""))) for c in candidates]
    return await provider.rerank(query, documents, top_k=top_k)


# ── Sync convenience bridge ──────────────────────────────────────────────────
_sync_loop: asyncio.AbstractEventLoop | None = None


def _get_sync_loop() -> asyncio.AbstractEventLoop:
    """Get or create a dedicated event loop for sync→async bridging."""
    global _sync_loop
    if _sync_loop is None or _sync_loop.is_closed():
        _sync_loop = asyncio.new_event_loop()
        _sync_loop.set_debug(False)
    return _sync_loop


def provider_generate_embedding_sync(text: str) -> list[float]:
    """Sync wrapper around provider_generate_embedding.

    Uses a dedicated event loop (not asyncio.run()) so that repeated
    calls from the same sync thread don't churn loop creation/destruction.
    Designed for use in anyio.to_thread contexts (MCP tool handlers, CLI).
    """
    loop = _get_sync_loop()
    return loop.run_until_complete(provider_generate_embedding(text))
