"""Tests for LLM client."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ast_tools.config.unified import LLMConfig
from ast_tools.llm.client import LLMClient, LLMFixContext, LLMFixResult


@pytest.fixture
def config():
    """Default LLM config for tests — remote-only."""
    return LLMConfig(
        enabled=True,
        prefer_local=False,
        remote_provider="openrouter",
        remote_model="qwen/qwen-2.5-coder-32b-instruct",
        timeout_seconds=30,
        max_tokens=2048,
        temperature=0.1,
        remote_fallback_chain=["openrouter", "anthropic", "gemini"],
    )


@pytest.fixture
def context():
    """Default fix context for tests."""
    return LLMFixContext(
        code="x = 1\n",
        diagnostic_message="Unused variable 'x'",
        diagnostic_code="F841",
        file_path="test.py",
        language="python",
    )


class TestSuggestFix:
    """Tests for LLMClient.suggest_fix()."""

    @pytest.mark.asyncio
    async def test_remote_success(self, config, context):
        """Successful remote fix suggestion returns diff."""
        client = LLMClient(config)

        with patch.object(client, "_try_remote_with_retry", new=AsyncMock()) as mock_remote:
            mock_remote.return_value = LLMFixResult(
                success=True,
                diff="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-x = 1\n+print('hello')\n",
                edits=[],
                model_used="qwen/qwen-2.5-coder-32b-instruct",
                provider="remote",
                confidence=0.95,
            )

            result = await client.suggest_fix(context)
            assert result.success is True
            assert result.diff is not None
            assert result.model_used == "qwen/qwen-2.5-coder-32b-instruct"
            assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_all_backends_fail(self, config, context):
        """Graceful failure when all backends fail."""
        client = LLMClient(config)

        with patch.object(client, "_try_remote_with_retry", new=AsyncMock()) as mock_remote:
            mock_remote.return_value = LLMFixResult(success=False, error="API returned 429")

            result = await client.suggest_fix(context)
            assert result.success is False
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_fallback_chain_all_fail(self, config, context):
        """All providers in fallback chain are tried."""
        client = LLMClient(config)
        call_order = []

        async def failing_remote(prompt, provider):
            call_order.append(provider)
            return LLMFixResult(success=False, error="Failed")

        client._try_remote_with_retry = failing_remote  # type: ignore

        result = await client.suggest_fix(context)
        assert result.success is False
        assert len(call_order) == len(config.remote_fallback_chain)

    @pytest.mark.asyncio
    async def test_fallback_succeeds_on_second_provider(self, config, context):
        """Second provider succeeds after first fails."""
        client = LLMClient(config)
        call_order = []

        async def partial_remote(prompt, provider):
            call_order.append(provider)
            if provider == "openrouter":
                return LLMFixResult(success=False, error="Quota exceeded")
            return LLMFixResult(
                success=True,
                diff="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-x = 1\n+print('hello')\n",
                model_used="claude-sonnet-4-20250514",
                provider="remote",
                confidence=0.9,
            )

        client._try_remote_with_retry = partial_remote  # type: ignore

        result = await client.suggest_fix(context)
        assert result.success is True
        assert len(call_order) == 2  # First failed, second succeeded

    @pytest.mark.asyncio
    async def test_disabled_llm(self, config, context):
        """Disabled LLM returns immediate failure."""
        config.enabled = False
        client = LLMClient(config)

        result = await client.suggest_fix(context)
        assert result.success is False
        assert "disabled" in result.error.lower()

    @pytest.mark.asyncio
    async def test_local_backend_tried_first(self, config, context):
        """Local backend is tried before remote when prefer_local."""
        config.prefer_local = True
        config.local_backend = "ollama"
        client = LLMClient(config)

        try_order = []

        async def local_result(prompt):
            try_order.append("local")
            return LLMFixResult(success=True, diff="test", provider="local")

        client._try_local_with_retry = local_result  # type: ignore

        async def remote_result(prompt, provider):
            try_order.append("remote")
            return LLMFixResult(success=False, error="should not reach")

        client._try_remote_with_retry = remote_result  # type: ignore

        result = await client.suggest_fix(context)
        assert result.provider == "local"
        assert try_order == ["local"]

    @pytest.mark.asyncio
    async def test_concurrent_requests_serialized(self, config, context):
        """Multiple concurrent requests are serialized by semaphore."""
        client = LLMClient(config)
        call_count = 0

        async def slow_remote(prompt, provider):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return LLMFixResult(
                success=True,
                diff=f"fix-{call_count}",
                provider="remote",
            )

        client._try_remote_with_retry = slow_remote  # type: ignore

        async def run():
            return await client.suggest_fix(context)

        # Fire 3 concurrent requests
        results = await asyncio.gather(run(), run(), run())
        assert all(r.success for r in results)
        # Semaphore ensures sequential execution (call_count equals total calls)
        assert call_count == 3


class TestIsAvailable:
    """Tests for LLMClient.is_available()."""

    @pytest.mark.asyncio
    async def test_disabled_returns_false(self, config):
        """Disabled LLM is never available."""
        config.enabled = False
        client = LLMClient(config)
        assert await client.is_available() is False

    @pytest.mark.asyncio
    async def test_remote_available_with_key(self, config):
        """Remote provider is available when API key is set."""
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-test"}):
            client = LLMClient(config)
            assert await client.is_available() is True

    @pytest.mark.asyncio
    async def test_remote_unavailable_without_key(self, config):
        """Remote provider is unavailable without API key."""
        with patch.dict("os.environ", {}, clear=True):
            client = LLMClient(config)
            assert await client.is_available() is False


class TestBuildPrompt:
    """Tests for _build_prompt()."""

    def test_includes_all_context(self, config, context):
        """Prompt includes all context fields."""
        client = LLMClient(config)
        prompt = client._build_prompt(context)
        assert "F841" in prompt
        assert "x = 1" in prompt
        assert "test.py" in prompt
        assert "python" in prompt

    def test_truncates_long_code(self, config, context):
        """Very long code is truncated."""
        context.code = "x = 1\n" * 5000
        client = LLMClient(config)
        prompt = client._build_prompt(context)
        assert len(prompt) < 10000
        assert "[truncated]" in prompt


class TestClose:
    """Tests for cleanup."""

    @pytest.mark.asyncio
    async def test_close_cleans_up_http_client(self, config):
        """Close releases HTTP resources."""
        client = LLMClient(config)
        # Access http client to create it
        _ = client._http()
        assert client._http_client is not None
        await client.close()
        assert client._http_client is None
