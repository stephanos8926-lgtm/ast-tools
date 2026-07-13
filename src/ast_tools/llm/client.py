"""Unified LLM client with local/remote backends and fallback chain."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from ast_tools.config.unified import LLMConfig

logger = logging.getLogger(__name__)


@dataclass
class LLMFixContext:
    """Context for an LLM fix suggestion request.

    Attributes:
        code: Source code snippet containing the issue
        diagnostic_message: Human-readable diagnostic (e.g. "Unused import os")
        diagnostic_code: Rule code (e.g. "F401")
        file_path: File path for context
        language: Language ID (python, typescript, etc.)
        context_lines: Lines of context to include
    """
    code: str
    diagnostic_message: str
    diagnostic_code: str
    file_path: str
    language: str
    context_lines: int = 20


@dataclass
class LLMFixResult:
    """Result of an LLM fix suggestion.

    Attributes:
        success: Whether the fix was generated successfully
        diff: Unified diff string, None if failed
        edits: Parsed TextEdit-style edits
        model_used: Which model generated the response
        provider: "local" or "remote"
        confidence: 0.0-1.0 confidence score
        error: Error message if failed
        token_usage: Token counts from the provider
    """
    success: bool
    diff: str | None = None
    edits: list[dict[str, Any]] = field(default_factory=list)
    model_used: str = ""
    provider: str = ""
    confidence: float = 0.0
    error: str | None = None
    token_usage: dict[str, int] | None = None


# Provider API endpoints
_PROVIDER_ENDPOINTS: dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
}

_PROVIDER_API_KEY_ENV: dict[str, str] = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


class LLMClient:
    """Unified LLM interface for generating fix suggestions.

    Supports local backends (Ollama, vLLM, llama.cpp) and remote providers
    (OpenRouter, Anthropic, Gemini) with configurable fallback chain.
    Concurrency is limited to 1 via asyncio.Semaphore to prevent
    bill shock from parallel API calls.

    Args:
        config: LLMConfig from UnifiedConfig.lsp.llm
    """

    def __init__(self, config: LLMConfig):
        self.config = config
        self._semaphore = asyncio.Semaphore(1)
        self._http_client: httpx.AsyncClient | None = None

    async def suggest_fix(self, context: LLMFixContext) -> LLMFixResult:
        """Generate a fix suggestion using configured backends.

        Tries local backend first (if enabled and prefer_local), then
        falls back through the remote provider chain. Each attempt uses
        exponential backoff on transient failures.

        Args:
            context: The fix context with code, diagnostic, and metadata

        Returns:
            LLMFixResult with diff, confidence, and model info
        """
        if not self.config.enabled:
            return LLMFixResult(success=False, error="LLM is disabled in config")

        async with self._semaphore:
            prompt = self._build_prompt(context)

            # Try local first if configured
            if self.config.prefer_local:
                result = await self._try_local_with_retry(prompt)
                if result.success:
                    return result

            # Fall back through remote chain
            for provider in self.config.remote_fallback_chain:
                result = await self._try_remote_with_retry(prompt, provider)
                if result.success:
                    return result

            return LLMFixResult(
                success=False,
                error="All LLM backends failed",
                model_used=self.config.remote_model,
            )

    async def is_available(self) -> bool:
        """Check if any backend is responsive (lightweight probe).

        For local backends, performs a real HTTP health check.
        For remote backends, checks if the API key env var is set.
        """
        if not self.config.enabled:
            return False

        if self.config.prefer_local:
            local_ok = await self._probe_local()
            if local_ok:
                return True

        for provider in self.config.remote_fallback_chain:
            remote_ok = await self._probe_remote(provider)
            if remote_ok:
                return True

        return False

    def _build_prompt(self, context: LLMFixContext) -> str:
        """Build prompt from context using config template or default.

        Truncates code to prevent token overflow.
        """
        code = context.code

        max_code = getattr(self.config, 'max_code_chars', 6000)
        if len(code) > max_code:
            code = code[:max_code] + "\n# ... [truncated]\n"

        return self.config.prompt_template.format(
            diagnostic_message=context.diagnostic_message,
            diagnostic_code=context.diagnostic_code,
            file_path=context.file_path,
            language=context.language,
            code_context=code,
        )

    async def _try_local_with_retry(self, prompt: str, attempt: int = 0) -> LLMFixResult:
        """Try local backend with exponential backoff."""
        max_attempts = 2
        backend = self.config.local_backend

        try:
            if backend == "ollama":
                return await self._call_ollama(prompt)
            elif backend == "vllm":
                return await self._call_vllm(prompt)
            elif backend == "llama.cpp":
                return await self._call_llamacpp(prompt)
            else:
                return LLMFixResult(success=False, error=f"Unknown backend: {backend}")
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt < max_attempts:
                wait = 2 ** attempt
                logger.warning("Local backend failed (%s), retrying in %ds", e, wait)
                await asyncio.sleep(wait)
                return await self._try_local_with_retry(prompt, attempt + 1)
            return LLMFixResult(success=False, error=f"Local backend failed: {e}")

    async def _try_remote_with_retry(self, prompt: str, provider: str, attempt: int = 0) -> LLMFixResult:
        """Try a remote provider with exponential backoff on 429/timeout."""
        max_attempts = 2

        try:
            return await self._call_remote(prompt, provider)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_attempts:
                retry_after = int(e.response.headers.get("Retry-After", str(2 ** attempt)))
                logger.warning("Rate limited on %s, retrying in %ds", provider, retry_after)
                await asyncio.sleep(retry_after)
                return await self._try_remote_with_retry(prompt, provider, attempt + 1)
            return LLMFixResult(
                success=False,
                error=f"{provider} returned {e.response.status_code}",
            )
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt < max_attempts:
                wait = 2 ** attempt
                logger.warning("%s failed (%s), retrying in %ds", provider, e, wait)
                await asyncio.sleep(wait)
                return await self._try_remote_with_retry(prompt, provider, attempt + 1)
            return LLMFixResult(success=False, error=f"{provider} network error: {e}")

    async def _call_ollama(self, prompt: str) -> LLMFixResult:
        """Call Ollama API."""
        async with self._http() as client:
            resp = await client.post(
                f"http://{self.config.local_host}:{self.config.local_port}/api/generate",
                json={"model": self.config.remote_model, "prompt": prompt, "stream": False},
                timeout=self.config.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            return LLMFixResult(
                success=True,
                diff=data.get("response", ""),
                provider="local",
                model_used=f"ollama:{self.config.remote_model}",
            )

    async def _call_vllm(self, prompt: str) -> LLMFixResult:
        """Call vLLM OpenAI-compatible API."""
        return LLMFixResult(success=False, error="vLLM requires CUDA (not available)")

    async def _call_llamacpp(self, prompt: str) -> LLMFixResult:
        """Call llama.cpp server API."""
        async with self._http() as client:
            resp = await client.post(
                f"http://{self.config.local_host}:{self.config.local_port}/completion",
                json={"prompt": prompt, "n_predict": self.config.max_tokens},
                timeout=self.config.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            return LLMFixResult(
                success=True,
                diff=data.get("content", ""),
                provider="local",
                model_used="llama.cpp",
            )

    async def _call_remote(self, prompt: str, provider: str) -> LLMFixResult:
        """Call a remote provider's API.

        Supports OpenRouter (OpenAI-compatible), Anthropic, and Gemini.
        Each provider reads its own API key from the environment.
        """
        api_key_env = _PROVIDER_API_KEY_ENV.get(provider)
        if not api_key_env:
            return LLMFixResult(success=False, error=f"Unknown provider: {provider}")

        import os
        api_key = os.environ.get(api_key_env)
        if not api_key:
            return LLMFixResult(
                success=False,
                error=f"{api_key_env} not set in environment",
            )

        endpoint = _PROVIDER_ENDPOINTS.get(provider)
        if not endpoint:
            return LLMFixResult(success=False, error=f"Unknown endpoint for: {provider}")

        async with self._http() as client:
            if provider == "openrouter":
                data = {
                    "model": self.config.remote_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": self.config.max_tokens,
                    "temperature": self.config.temperature,
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": (
                        "https://github.com/stephanos8926-lgtm/ast-tools"
                    ),
                }
                resp = await client.post(
                    endpoint, json=data, headers=headers,
                    timeout=self.config.timeout_seconds,
                )
                resp.raise_for_status()
                result_data = resp.json()
                choices = result_data.get("choices", [])
                content = (
                    choices[0].get("message", {}).get("content", "")
                    if choices
                    else ""
                )
                usage = result_data.get("usage", {})
                return LLMFixResult(
                    success=True,
                    diff=content,
                    provider="remote",
                    model_used=self.config.remote_model,
                    token_usage={
                        "prompt": usage.get("prompt_tokens", 0),
                        "completion": usage.get("completion_tokens", 0),
                        "total": usage.get("total_tokens", 0),
                    },
                )

            elif provider == "anthropic":
                data = {
                    "model": "claude-sonnet-4-20250514",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": self.config.max_tokens,
                }
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                resp = await client.post(
                    endpoint, json=data, headers=headers,
                    timeout=self.config.timeout_seconds,
                )
                resp.raise_for_status()
                result_data = resp.json()
                content_blocks = result_data.get("content", [])
                content = content_blocks[0].get("text", "") if content_blocks else ""
                usage = result_data.get("usage", {})
                return LLMFixResult(
                    success=True,
                    diff=content,
                    provider="remote",
                    model_used="claude-sonnet-4-20250514",
                    token_usage={
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                    },
                )

            elif provider == "gemini":
                model = "gemini-2.5-flash"
                url = endpoint.format(model=model)
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": self.config.max_tokens,
                        "temperature": self.config.temperature,
                    },
                }
                resp = await client.post(
                    f"{url}?key={api_key}", json=data,
                    timeout=self.config.timeout_seconds,
                )
                resp.raise_for_status()
                result_data = resp.json()
                candidates = result_data.get("candidates", [])
                content = ""
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    content = "".join(p.get("text", "") for p in parts)
                usage = result_data.get("usageMetadata", {})
                return LLMFixResult(
                    success=True,
                    diff=content,
                    provider="remote",
                    model_used=model,
                    token_usage={
                        "prompt": usage.get("promptTokenCount", 0),
                        "completion": usage.get("candidatesTokenCount", 0),
                        "total": usage.get("totalTokenCount", 0),
                    },
                )

            return LLMFixResult(success=False, error=f"Unimplemented provider: {provider}")

    async def _probe_local(self) -> bool:
        """Probe local backend availability (lightweight)."""
        try:
            async with self._http() as client:
                if self.config.local_backend == "ollama":
                    resp = await client.get(
                        f"http://{self.config.local_host}:{self.config.local_port}/api/tags",
                        timeout=5,
                    )
                    return resp.status_code == 200
                elif self.config.local_backend == "llama.cpp":
                    resp = await client.get(
                        f"http://{self.config.local_host}:{self.config.local_port}/health",
                        timeout=5,
                    )
                    return resp.status_code == 200
        except Exception:
            pass
        return False

    async def _probe_remote(self, provider: str) -> bool:
        """Probe remote provider availability (just check API key exists)."""
        import os
        api_key_env = _PROVIDER_API_KEY_ENV.get(provider)
        if api_key_env and os.environ.get(api_key_env):
            return True
        return False

    def _http(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
        return self._http_client

    async def close(self):
        """Close underlying HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
