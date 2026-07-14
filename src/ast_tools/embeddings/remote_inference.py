"""Remote inference client for RW_InferenceEngine.

Provides async HTTP client for connecting to the remote embedding/reranking
microservice with connection pooling, retries, and health checks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class RemoteInferenceConfig:
    """Configuration for remote inference client."""

    base_url: str = "http://localhost:3000"
    # Connection pooling
    connector_limit: int = 10
    connector_limit_per_host: int = 5
    # Timeouts
    request_timeout: float = 30.0
    connect_timeout: float = 10.0
    # Retries
    max_retries: int = 3
    retry_backoff: float = 1.0
    # Health check
    health_check_interval: float = 30.0
    # Headers
    user_agent: str = "ast-tools/remote-inference"

    @classmethod
    def from_env(cls) -> "RemoteInferenceConfig":
        """Create config from environment variables."""
        return cls(
            base_url=os.environ.get("AST_TOOLS_REMOTE_INFERENCE_URL", "http://localhost:3000"),
            connector_limit=int(os.environ.get("AST_TOOLS_REMOTE_CONNECTOR_LIMIT", "10")),
            request_timeout=float(os.environ.get("AST_TOOLS_REMOTE_TIMEOUT", "30.0")),
            max_retries=int(os.environ.get("AST_TOOLS_REMOTE_MAX_RETRIES", "3")),
            health_check_interval=float(os.environ.get("AST_TOOLS_REMOTE_HEALTH_INTERVAL", "30.0")),
        )

    @property
    def embeddings_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/v1/embeddings"

    @property
    def rerank_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/v1/rerank"

    @property
    def health_live_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/health/live"

    @property
    def health_ready_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/health/ready"


@dataclass
class RemoteInferenceClient:
    """Async HTTP client for remote inference engine."""

    config: RemoteInferenceConfig
    _session: aiohttp.ClientSession | None = field(default=None, init=False)
    _healthy: bool = field(default=False, init=False)
    _last_health_check: float = field(default=0.0, init=False)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with connection pooling."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=self.config.request_timeout,
                connect=self.config.connect_timeout,
            )
            connector = aiohttp.TCPConnector(
                limit=self.config.connector_limit,
                limit_per_host=self.config.connector_limit_per_host,
                keepalive_timeout=30,
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={"User-Agent": self.config.user_agent},
            )
        return self._session

    async def _request_with_retry(
        self, method: str, url: str, **kwargs
    ) -> dict[str, Any]:
        """Make HTTP request with exponential backoff retry."""
        session = await self._get_session()
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                async with session.request(method, url, **kwargs) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        # Rate limited - wait and retry
                        retry_after = float(response.headers.get("Retry-After", "1"))
                        await asyncio.sleep(retry_after)
                        continue
                    elif response.status >= 500:
                        # Server error - retry
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=await response.text(),
                        )
                    else:
                        # Client error - don't retry
                        text = await response.text()
                        raise ValueError(f"HTTP {response.status}: {text}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                if attempt < self.config.max_retries:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}. "
                        f"Retrying in {self.config.retry_backoff * (2**attempt)}s..."
                    )
                    await asyncio.sleep(self.config.retry_backoff * (2**attempt))
                    continue
                else:
                    logger.error(f"Request failed after {self.config.max_retries + 1} attempts: {e}")
                    raise

        raise last_exception

    async def health_check(self, force: bool = False) -> bool:
        """Check if remote inference engine is healthy.

        Caches result for health_check_interval seconds unless force=True.
        """
        now = time.time()
        if not force and self._healthy and (now - self._last_health_check) < self.config.health_check_interval:
            return self._healthy

        try:
            session = await self._get_session()
            async with session.get(self.config.health_ready_url) as response:
                if response.status == 200:
                    data = await response.json()
                    self._healthy = data.get("models_loaded", False)
                else:
                    self._healthy = False
            self._last_health_check = now
            if self._healthy:
                logger.debug("Remote inference health check: HEALTHY")
            else:
                logger.warning("Remote inference health check: NOT READY")
        except Exception as e:
            self._healthy = False
            self._last_health_check = now
            logger.warning(f"Remote inference health check error: {e}")
        return self._healthy

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        if not await self.health_check():
            raise RuntimeError("Remote inference engine is not healthy")

        data = await self._request_with_retry(
            "POST",
            self.config.embeddings_url,
            json={"input": text},
        )
        return data["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not await self.health_check():
            raise RuntimeError("Remote inference engine is not healthy")

        data = await self._request_with_retry(
            "POST",
            self.config.embeddings_url,
            json={"input": texts},
        )
        # Handle both single and batch response formats
        if "embedding" in data:
            return [data["embedding"]]
        return [item["embedding"] for item in data["data"]]

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[float]:
        """Rerank documents by relevance to query."""
        if not documents:
            return []

        payload = {"query": query, "documents": documents}
        if top_k is not None:
            payload["top_k"] = top_k

        result = await self._request_with_retry("POST", self.config.rerank_url, json=payload)
        scores = result.get("scores", [])
        return scores

    async def get_model_info(self) -> dict:
        """Get information about loaded models."""
        if not await self.health_check():
            raise RuntimeError("Remote inference engine is not healthy")

        response = await self._request_with_retry("GET", self.config.health_ready_url)
        return response.json()

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "RemoteInferenceClient":
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()