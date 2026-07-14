"""Remote inference client for RW_InferenceEngine.

Provides HTTP client for remote embedding and reranking via the RW_InferenceEngine
microservice. Supports connection pooling, retries, and health checks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
import httpx

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RemoteInferenceConfig:
    """Configuration for remote inference client."""

    base_url: str = "http://100.126.48.57:8300"
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    health_check_interval_seconds: float = 60.0
    verify_ssl: bool = True

    @classmethod
    def from_env(cls) -> "RemoteInferenceConfig":
        """Create config from environment variables."""
        return cls(
            base_url=os.environ.get("AST_TOOLS_REMOTE_INFERENCE_URL", "http://100.126.48.57:8300"),
            timeout_seconds=float(os.environ.get("AST_TOOLS_REMOTE_TIMEOUT", "30")),
            max_retries=int(os.environ.get("AST_TOOLS_REMOTE_MAX_RETRIES", "3")),
            retry_delay_seconds=float(os.environ.get("AST_TOOLS_REMOTE_RETRY_DELAY", "1.0")),
            health_check_interval_seconds=float(os.environ.get("AST_TOOLS_REMOTE_HEALTH_INTERVAL", "60")),
            verify_ssl=os.environ.get("AST_TOOLS_REMOTE_VERIFY_SSL", "true").lower() == "true",
        )


class RemoteInferenceError(Exception):
    """Raised when remote inference fails."""

    pass


class RemoteInferenceClient:
    """Async HTTP client for RW_InferenceEngine remote inference."""

    def __init__(self, config: RemoteInferenceConfig | None = None):
        self.config = config or RemoteInferenceConfig.from_env()
        self._client: httpx.AsyncClient | None = None
        self._last_health_check = 0.0
        self._is_healthy = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=30.0,
            )
            timeout = httpx.Timeout(self.config.timeout_seconds)
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                limits=limits,
                timeout=timeout,
                verify=self.config.verify_ssl,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self, force: bool = False) -> bool:
        """Check if the remote inference engine is healthy.

        Args:
            force: Skip cache and force new health check

        Returns:
            True if healthy, False otherwise
        """
        now = time.time()
        if not force and (now - self._last_health_check) < self.config.health_check_interval_seconds:
            return self._is_healthy

        try:
            client = await self._get_client()
            response = await client.get("/health/live", timeout=5.0)
            self._is_healthy = response.status_code == 200
            self._last_health_check = now
            if self._is_healthy:
                logger.debug("Remote inference health check: HEALTHY")
            else:
                logger.warning(f"Remote inference health check failed: {response.status_code}")
        except Exception as e:
            self._is_healthy = False
            self._last_health_check = now
            logger.warning(f"Remote inference health check error: {e}")
        return self._is_healthy

    async def _request_with_retry(
        self, method: str, path: str, **kwargs
    ) -> httpx.Response:
        """Make HTTP request with retry logic."""
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < self.config.max_retries:
                    logger.warning(f"Remote inference request failed (attempt {attempt + 1}), retrying...")
                    await asyncio.sleep(self.config.retry_delay_seconds * (attempt + 1))
                else:
                    break
            except httpx.HTTPStatusError as e:
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise RemoteInferenceError(f"Remote inference error: {e.response.text}") from e
                last_error = e
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay_seconds * (attempt + 1))
                else:
                    break
        raise RemoteInferenceError(f"Remote inference failed after {self.config.max_retries + 1} attempts: {last_error}")

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (384 dimensions for bge-small-en-v1.5)
        """
        if not await self.health_check():
            raise RemoteInferenceError("Remote inference engine is not healthy")

        response = await self._request_with_retry(
            "POST",
            "/v1/embeddings",
            json={"input": text},
        )
        data = response.json()
        return data["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not await self.health_check():
            raise RemoteInferenceError("Remote inference engine is not healthy")

        response = await self._request_with_retry(
            "POST",
            "/v1/embeddings",
            json={"input": texts},
        )
        data = response.json()
        # Handle both single and batch response formats
        if "embedding" in data:
            return [data["embedding"]]
        return [item["embedding"] for item in data["data"]]

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        """Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: List of document texts

        Returns:
            List of relevance scores (one per document)
        """
        if not await self.health_check():
            raise RemoteInferenceError("Remote inference engine is not healthy")

        response = await self._request_with_retry(
            "POST",
            "/v1/rerank",
            json={"query": query, "documents": documents},
        )
        data = response.json()
        return data["scores"]

    async def get_model_info(self) -> dict:
        """Get information about loaded models."""
        if not await self.health_check():
            raise RemoteInferenceError("Remote inference engine is not healthy")

        response = await self._request_with_retry("GET", "/health/ready")
        return response.json()


# Global client instance (lazy-initialized)
_global_client: RemoteInferenceClient | None = None


def get_remote_client(config: RemoteInferenceConfig | None = None) -> RemoteInferenceClient:
    """Get or create the global remote inference client."""
    global _global_client
    if _global_client is None:
        _global_client = RemoteInferenceClient(config)
    return _global_client


async def close_remote_client() -> None:
    """Close the global remote inference client."""
    global _global_client
    if _global_client is not None:
        await _global_client.close()
        _global_client = None