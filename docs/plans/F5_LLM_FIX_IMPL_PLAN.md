# F5 — LLM Fix System Implementation Plan

> **Mode:** MEDIUM
> **For Hermes:** Use plan-and-audit skill with phase-by-phase execution. TDD mandatory for all phases.
> **Total:** ~12h split across 5 phases

**Goal:** Build an LLM-powered fix suggestion system exposed through MCP tool, CLI, and LSP bridge, sharing a single LLMClient core.

**Architecture:** Core LLM layer (`ast_tools/llm/`) → three consumer channels (MCP tool, CLI flag, LSP bridge). Config already exists in `UnifiedConfig.lsp.llm`.

**Tech Stack:** httpx (HTTP), stdlib `difflib` (diff parsing), `lsprotocol` (LSP types)

---

## Phase A: Core LLM Layer (4h)

### Task A.1: Add httpx to pyproject.toml

**Objective:** Declare httpx as explicit dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Edit pyproject.toml**

Add httpx to `[project.dependencies]`.

**Step 2: Verify**

Run: `cd ~/Workspaces/ast-tools && pip install -e . 2>&1 | tail -5`
Expected: No errors.

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore(deps): add httpx dependency for LLM client"
```

---

### Task A.2: Create llm/package skeleton

**Objective:** Create the `ast_tools/llm/` package with `__init__.py`

**Files:**
- Create: `src/ast_tools/llm/__init__.py`

**Content:**

```python
"""LLM-powered fix generation and analysis."""
from .client import LLMClient, LLMFixContext, LLMFixResult
from .prompts import Prompts
from .diff_parser import parse_and_validate_diff, ParseResult

__all__ = [
    "LLMClient", "LLMFixContext", "LLMFixResult",
    "Prompts", "parse_and_validate_diff", "ParseResult",
]
```

**Verification:**

Run: `cd ~/Workspaces/ast-tools && python3 -c "from ast_tools.llm import LLMClient; print('OK')"`
Expected: ImportError (no client.py yet) — that's expected for now.

---

### Task A.3: Create llm/diff_parser.py (TDD)

**Objective:** Parse and validate unified diffs from LLM responses

**Files:**
- Create: `src/ast_tools/llm/diff_parser.py`
- Create: `tests/test_llm_diff_parser.py`

**Step 1: Write failing test**

```python
"""Tests for LLM diff parser."""

from ast_tools.llm.diff_parser import parse_and_validate_diff, ParseResult


def test_parse_simple_diff():
    """Parse a simple unified diff."""
    original = "x = 1\n"
    diff_text = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    
    result = parse_and_validate_diff(diff_text, original)
    
    assert result.success is True
    assert len(result.edits) == 1
    assert result.applied_text == "x = 2\n"
    assert result.parsed_hunks == 1
    assert result.matched_hunks == 1


def test_parse_diff_no_match():
    """Diff that doesn't match original content."""
    original = "y = 1\n"
    diff_text = "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    
    result = parse_and_validate_diff(diff_text, original)
    
    assert result.success is False
    assert result.error is not None


def test_parse_multiline_diff():
    """Diff with multiple hunks."""
    original = "import os\nimport sys\n\nx = 1\n"
    diff_text = (
        "--- a/test.py\n+++ b/test.py\n"
        "@@ -1,2 +1,1 @@\n-import os\n-import sys\n+import os, sys\n"
        "@@ -3,2 +2,2 @@\n-x = 1\n+y = 1\n"
    )
    
    result = parse_and_validate_diff(diff_text, original)
    
    assert result.success is True
    assert result.parsed_hunks == 2


def test_parse_empty_diff():
    """Empty diff string."""
    result = parse_and_validate_diff("", "content")
    assert result.success is False
    assert "empty" in result.error.lower()


def test_parse_malformed_diff():
    """Completely malformed diff."""
    result = parse_and_validate_diff("this is not a diff", "content")
    assert result.success is False


def test_parse_diff_confidence_scoring():
    """Verify confidence reflects context match quality."""
    original = "x = 1\ny = 2\nz = 3\n"
    diff_perfect = (
        "--- a/test.py\n+++ b/test.py\n"
        "@@ -1,3 +1,3 @@\n x = 1\n-y = 2\n+z = 2\n z = 3\n"
    )
    
    result = parse_and_validate_diff(diff_perfect, original)
    assert result.confidence > 0.9
```

**Step 2: Verify failure**

Run: `cd ~/Workspaces/ast-tools && python3 -m pytest tests/test_llm_diff_parser.py -v`
Expected: ImportError — module doesn't exist

**Step 3: Implement diff_parser.py**

```python
"""Parse and validate unified diffs from LLM suggestions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParseResult:
    """Result of parsing and validating a unified diff."""
    success: bool
    edits: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    error: str | None = None
    parsed_hunks: int = 0
    matched_hunks: int = 0
    applied_text: str | None = None


_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@")
_DIFF_LINE_RE = re.compile(r"^([ +-\\])")


def parse_and_validate_diff(
    diff_text: str,
    original_content: str,
    file_extension: str = ".py",
) -> ParseResult:
    """Parse a unified diff and validate it applies cleanly.
    
    Args:
        diff_text: Unified diff string from LLM response
        original_content: Original file content to validate against
        file_extension: File extension for syntax validation (unused in v1)
    
    Returns:
        ParseResult with parsed edits, confidence, and validation status
    """
    if not diff_text or not diff_text.strip():
        return ParseResult(success=False, error="Empty diff text")
    
    lines = original_content.splitlines(keepends=True)
    
    # Split into hunks
    hunks = _parse_hunks(diff_text)
    if not hunks:
        return ParseResult(success=False, error="No hunks found in diff")
    
    total_confidence = 0.0
    all_edits = []
    matched = 0
    
    for hunk in hunks:
        result = _apply_hunk(hunk, lines)
        if result.success:
            matched += 1
            total_confidence += result.confidence
            if result.modified_lines:
                all_edits.extend(result.modified_lines)
        # If a hunk fails, we still try the others
    
    if matched == 0:
        return ParseResult(
            success=False,
            error="No hunks matched the original content",
            parsed_hunks=len(hunks),
            matched_hunks=0,
            confidence=0.0,
        )
    
    # Reconstruct the full content
    applied_text = "".join(lines)
    
    # Confidence = proportion of matched hunks * average context match
    avg_confidence = total_confidence / len(hunks) if hunks else 0.0
    
    return ParseResult(
        success=True,
        edits=all_edits,
        confidence=avg_confidence,
        parsed_hunks=len(hunks),
        matched_hunks=matched,
        applied_text=applied_text,
    )


def _parse_hunks(diff_text: str) -> list[dict]:
    """Split diff into individual hunks."""
    hunks = []
    current_hunk = None
    
    for line in diff_text.splitlines():
        match = _HUNK_HEADER_RE.match(line)
        if match:
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = {
                "old_start": int(match.group(1)),
                "old_count": int(match.group(2)) if match.group(2) else 1,
                "new_start": int(match.group(3)),
                "new_count": int(match.group(4)) if match.group(4) else 1,
                "context_before": [],
                "removed": [],
                "added": [],
                "context_after": [],
                "phase": "context_before",
            }
        elif current_hunk:
            if line.startswith(" "):
                # Context line
                content = line[1:]  # Remove leading space
                current_hunk[current_hunk["phase"]].append(content)
            elif line.startswith("-"):
                current_hunk["removed"].append(line[1:])
                current_hunk["phase"] = "removed"
            elif line.startswith("+"):
                current_hunk["added"].append(line[1:])
                current_hunk["phase"] = "added"
            elif line.startswith("\\"):
                # No newline at end of file marker — skip
                pass
    
    if current_hunk:
        hunks.append(current_hunk)
    
    return hunks


def _apply_hunk(hunk: dict, lines: list[str]) -> ParseResult:
    """Apply a single hunk to the lines array. Modifies lines in place."""
    total_lines = len(lines)
    old_start = hunk["old_start"] - 1  # Convert to 0-indexed
    
    context_before = hunk["context_before"]
    removed = hunk["removed"]
    added = hunk["added"]
    context_after = hunk["context_after"]
    
    # Verify context before
    for i, ctx_line in enumerate(context_before):
        idx = old_start + i
        if idx >= total_lines or lines[idx].rstrip("\n") != ctx_line.rstrip("\n"):
            return ParseResult(success=False, error="Context mismatch before changes")
    
    # Verify removed lines
    for i, rem_line in enumerate(removed):
        idx = old_start + len(context_before) + i
        if idx >= total_lines or lines[idx].rstrip("\n") != rem_line.rstrip("\n"):
            return ParseResult(success=False, error="Removed lines don't match")
    
    # Verify context after
    after_start = old_start + len(context_before) + len(removed)
    for i, ctx_line in enumerate(context_after):
        idx = after_start + i
        if idx >= total_lines or lines[idx].rstrip("\n") != ctx_line.rstrip("\n"):
            return ParseResult(success=False, error="Context mismatch after changes")
    
    # Apply the change: replace removed lines with added lines
    start = old_start + len(context_before)
    end = start + len(removed)
    
    # Calculate confidence based on context match
    total_context = len(context_before) + len(context_after)
    confidence = min(1.0, total_context / max(1, total_context + len(removed)))
    
    # Track the edit
    edit = {
        "start_line": start,
        "end_line": end,
        "old_text": "".join(removed),
        "new_text": "".join(added),
    }
    
    # Apply in-place
    lines[start:end] = [a + ("\n" if not a.endswith("\n") else "") for a in added]
    
    return ParseResult(
        success=True,
        edits=[edit],
        confidence=confidence,
        parsed_hunks=1,
        matched_hunks=1,
        applied_text="".join(lines),
    )
```

**Step 4: Verify tests pass**

```bash
cd ~/Workspaces/ast-tools
python3 -m pytest tests/test_llm_diff_parser.py -v
```

Expected: All tests pass.

**Step 5: Commit**

```bash
git add src/ast_tools/llm/diff_parser.py tests/test_llm_diff_parser.py
git commit -m "feat(llm): add diff parser for validating LLM suggestions"
```

---

### Task A.4: Create llm/prompts.py (TDD)

**Objective:** Structured prompt templates for LLM fix generation

**Files:**
- Create: `src/ast_tools/llm/prompts.py`
- Create: `tests/test_llm_prompts.py`

**Step 1: Write failing test (sample):**

```python
from ast_tools.llm.prompts import Prompts


def test_fix_suggestion_contains_diagnostic():
    prompt = Prompts.fix_suggestion(
        code="x = 1\n",
        diagnostic_message="Unused variable 'x'",
        diagnostic_code="F841",
        file_path="test.py",
        language="python",
    )
    assert "F841" in prompt
    assert "x = 1" in prompt
    assert "unified diff" in prompt


def test_fix_suggestion_truncates_long_code():
    code = "x = 1\n" * 5000  # Very long code
    prompt = Prompts.fix_suggestion(
        code=code,
        diagnostic_message="Test",
        diagnostic_code="E001",
        file_path="test.py",
        language="python",
    )
    # Should not exceed ~8000 chars
    assert len(prompt) < 10000
```

**Step 2: Implement prompts.py**

```python
"""Structured prompt templates for LLM fix generation."""

from __future__ import annotations


class Prompts:
    """Prompt templates for LLM fix generation."""
    
    MAX_CODE_CHARS = 6000  # Truncate code to avoid token overflow
    
    @staticmethod
    def fix_suggestion(
        code: str,
        diagnostic_message: str,
        diagnostic_code: str,
        file_path: str,
        language: str,
    ) -> str:
        """Build the fix suggestion prompt."""
        # Truncate code if too long
        if len(code) > Prompts.MAX_CODE_CHARS:
            code = code[:Prompts.MAX_CODE_CHARS] + "\n# ... [truncated]\n"
        
        return (
            "You are an expert code reviewer and fixer. Given a diagnostic and "
            "the surrounding code context, suggest the minimal, correct fix.\n\n"
            f"Diagnostic: {diagnostic_message}\n"
            f"Rule: {diagnostic_code}\n"
            f"File: {file_path}\n"
            f"Language: {language}\n\n"
            "Code context:\n"
            f"```{language}\n{code}```\n\n"
            "Return ONLY the unified diff that fixes the issue. "
            "Use standard unified diff format with lines starting with + and -. "
            "Be minimal — only change what's needed to fix the diagnostic."
        )
```

**Step 3-5:** Create tests, verify pass, commit.

---

### Task A.5: Create llm/client.py (TDD)

**Objective:** LLMClient with local/remote backends, fallback chain, retry logic

**Files:**
- Create: `src/ast_tools/llm/client.py`
- Create: `tests/test_llm_client.py`

**Step 1: Write test (sample):**

```python
"""Tests for LLM client."""
from unittest.mock import AsyncMock, patch

import pytest

from ast_tools.config.unified import LLMConfig
from ast_tools.llm.client import LLMClient, LLMFixContext, LLMFixResult


@pytest.fixture
def config():
    return LLMConfig(
        enabled=True,
        prefer_local=False,  # Remote only (workstation constraint)
        remote_provider="openrouter",
        remote_model="qwen/qwen-2.5-coder-32b-instruct",
        timeout_seconds=30,
        max_tokens=2048,
        temperature=0.1,
    )


@pytest.mark.asyncio
async def test_suggest_fix_remote_success(config):
    """Test successful remote fix suggestion."""
    client = LLMClient(config)
    context = LLMFixContext(
        code="x = 1\n",
        diagnostic_message="Unused variable",
        diagnostic_code="F841",
        file_path="test.py",
        language="python",
    )
    
    with patch.object(client, '_try_remote', new=AsyncMock()) as mock_remote:
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


@pytest.mark.asyncio
async def test_suggest_fix_all_backends_fail(config):
    """Test graceful failure when all backends fail."""
    client = LLMClient(config)
    context = LLMFixContext(
        code="x = 1\n",
        diagnostic_message="Test",
        diagnostic_code="E001",
        file_path="test.py",
        language="python",
    )
    
    with patch.object(client, '_try_remote', new=AsyncMock()) as mock_remote:
        mock_remote.return_value = LLMFixResult(
            success=False, error="API returned 429"
        )
        
        result = await client.suggest_fix(context)
        assert result.success is False
        assert result.error is not None


@pytest.mark.asyncio
async def test_fallback_chain(config):
    """Test fallback through providers."""
    client = LLMClient(config)
    context = LLMFixContext(
        code="x = 1\n", diagnostic_message="Test",
        diagnostic_code="E001", file_path="test.py", language="python",
    )
    call_order = []
    
    async def failing_remote(prompt, provider):
        call_order.append(provider)
        return LLMFixResult(success=False, error="Failed")
    
    client._try_remote = failing_remote
    
    result = await client.suggest_fix(context)
    assert result.success is False
    # Should have tried all providers in the chain
    assert len(call_order) == len(config.remote_fallback_chain)


@pytest.mark.asyncio
async def test_disabled_llm(config):
    """Test LLM disabled."""
    config.enabled = False
    client = LLMClient(config)
    context = LLMFixContext(
        code="x = 1\n", diagnostic_message="Test",
        diagnostic_code="E001", file_path="test.py", language="python",
    )
    
    result = await client.suggest_fix(context)
    assert result.success is False
    assert "disabled" in result.error.lower()
```

**Step 2: Implement client.py**

```python
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
    """Context for an LLM fix suggestion request."""
    code: str
    diagnostic_message: str
    diagnostic_code: str
    file_path: str
    language: str
    context_lines: int = 20


@dataclass
class LLMFixResult:
    """Result of an LLM fix suggestion."""
    success: bool
    diff: str | None = None
    edits: list[dict[str, Any]] = field(default_factory=list)
    model_used: str = ""
    provider: str = ""
    confidence: float = 0.0
    error: str | None = None
    token_usage: dict[str, int] | None = None


# Provider API endpoints
_PROVIDER_ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
}

_PROVIDER_API_KEY_ENV = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


class LLMClient:
    """Unified LLM interface for generating fix suggestions.
    
    Supports local backends (Ollama, vLLM, llama.cpp) and remote providers
    (OpenRouter, Anthropic, Gemini) with configurable fallback chain.
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._semaphore = asyncio.Semaphore(1)  # Max 1 concurrent call
        self._http_client: httpx.AsyncClient | None = None
    
    async def suggest_fix(self, context: LLMFixContext) -> LLMFixResult:
        """Generate a fix suggestion using configured backends.
        
        Tries local backend first (if enabled + prefer_local), then falls
        back through the remote provider chain. Each attempt uses
        exponential backoff on transient failures.
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
        """Check if any backend is responsive (lightweight probe)."""
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
        """Build prompt from context using config template or default."""
        template = self.config.prompt_template
        code = context.code
        
        # Truncate code to avoid token overflow
        max_code = getattr(self.config, 'max_code_chars', 6000)
        if len(code) > max_code:
            code = code[:max_code] + "\n# ... [truncated]\n"
        
        return template.format(
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
            return LLMFixResult(success=False, error=f"{provider} returned {e.response.status_code}")
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
                json={"model": "codellama", "prompt": prompt, "stream": False},
                timeout=self.config.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            return LLMFixResult(
                success=True, diff=data.get("response", ""),
                provider="local", model_used=f"ollama:codelama",
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
                success=True, diff=data.get("content", ""),
                provider="local", model_used="llama.cpp",
            )
    
    async def _call_remote(self, prompt: str, provider: str) -> LLMFixResult:
        """Call a remote provider's API."""
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
                    "HTTP-Referer": "https://github.com/stephanos8926-lgtm/ast-tools",
                }
                resp = await client.post(
                    endpoint, json=data, headers=headers,
                    timeout=self.config.timeout_seconds,
                )
                resp.raise_for_status()
                result = resp.json()
                choices = result.get("choices", [])
                content = choices[0].get("message", {}).get("content", "") if choices else ""
                usage = result.get("usage", {})
                return LLMFixResult(
                    success=True, diff=content,
                    provider="remote", model_used=self.config.remote_model,
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
                result = resp.json()
                content = result.get("content", [{}])[0].get("text", "")
                usage = result.get("usage", {})
                return LLMFixResult(
                    success=True, diff=content,
                    provider="remote", model_used="claude-sonnet-4-20250514",
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
                result = resp.json()
                candidates = result.get("candidates", [])
                content = ""
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    content = "".join(p.get("text", "") for p in parts)
                usage = result.get("usageMetadata", {})
                return LLMFixResult(
                    success=True, diff=content,
                    provider="remote", model_used=model,
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
```

**Step 3-5:** Run tests, commit.

---

## Phase B: MCP Tool + CLI Flag (2h)

### Task B.1: Create llm_suggest_fix MCP tool

**Files:**
- Create: `src/ast_tools/tools/llm_suggest_fix.py`
- Modify: `src/ast_tools/tools/__init__.py` (register tool)
- Create: `tests/test_llm_suggest_fix.py`

**Content:** Follow the pattern from `fix_mcp.py` — `_tool_llm_suggest_fix(name, params)` that:
1. Extracts code, diagnostic, diagnostic_code, file_path, language from params
2. Creates LLMFixContext
3. Creates LLMClient with config from `load_unified_config()`
4. Calls `client.suggest_fix(context)`
5. Returns structured result with diff, confidence, model info

Register in `tools/__init__.py`:
```python
from .llm_suggest_fix import _tool_llm_suggest_fix
register_tool("llm_suggest_fix", _tool_llm_suggest_fix, schema)
```

### Task B.2: Add --llm flag to CLI fix command

**Files:**
- Modify: `src/ast_tools/cli.py`
- Add `--llm` flag to `cmd_fix` parser

---

## Phase C: LSP Bridge (2h)

### Task C.1: Create lsp/llm_bridge.py

**Files:**
- Create: `src/ast_tools/lsp/llm_bridge.py`
- Modify: `src/ast_tools/lsp/code_actions.py` (wire into resolve)
- Modify: `src/ast_tools/lsp/server.py` (wire bridge)

### Task C.2: Wire into code_actions.py

Replace the stub `resolve_code_action()` with LLM bridge call when `action.data` indicates `llm_fix` type.

---

## Phase D: Full Test Suite (3h)

### Test Files

| File | Tests | What it verifies |
|------|-------|------------------|
| `tests/test_llm_diff_parser.py` | 8 | Parse valid/invalid/empty/malformed diffs, confidence scoring, multi-hunk |
| `tests/test_llm_prompts.py` | 4 | Prompt structure, truncation, diagnostic inclusion |
| `tests/test_llm_client.py` | 6 | Success path, fallback chain, disabled, all-backends-fail, concurrency |
| `tests/test_llm_suggest_fix.py` | 3 | Tool registration, schema validity, error handling |

### Integration Test (manual)

```bash
# Requires OPENROUTER_API_KEY in environment
OPENROUTER_API_KEY=sk-... ast-tools tools/call llm_suggest_fix '{"code": "x = 1", "diagnostic": "unused variable", "diagnostic_code": "F841", "file_path": "test.py", "language": "python"}'
```

---

## Phase E: Audit (2h)

Run adversarial, bug review, lint, and test/perf verification per plan-and-audit MEDIUM mode checklist.

---

## Rollback Plan

| Phase | Rollback |
|-------|----------|
| Phase A (Core LLM) | Remove `src/ast_tools/llm/` directory, revert httpx in pyproject.toml |
| Phase B (MCP Tool) | Revert `tools/__init__.py`, delete `tools/llm_suggest_fix.py` |
| Phase C (LSP Bridge) | Delete `lsp/llm_bridge.py`, revert `code_actions.py` |
| Phase D (Tests) | Delete `tests/test_llm_*.py` |
| All | `git revert` each phase commit in reverse order |
