# F5 — LLM Fix System: Agent-Facing + IDE Code Actions

**Feature:** F5
**Mode:** MEDIUM
**Duration:** 3 days
**Status:** Spec in progress

---

## Overview

Build an LLM-powered fix suggestion system that generates validated patches from code + diagnostic context. Exposed through **three channels** — MCP tool for Hermes agent, CLI for terminal use, and LSP bridge for IDE code actions — sharing a single `LLMClient` core.

The `LLMConfig` already exists in `UnifiedConfig.lsp.llm` with local (llama.cpp/ollama/vllm) and remote (OpenRouter/Anthropic/Gemini) backends, fallback chain, and prompt template. This spec builds the runtime layer on top of it.

---

## Architecture

```
src/ast_tools/llm/                  ← Core (new package)
  __init__.py                        Exports
  client.py                          LLMClient — local/remote backends, fallback chain
  prompts.py                         Structured prompt templates  
  diff_parser.py                     Validate LLM diffs → TextEdits

src/ast_tools/tools/
  llm_suggest_fix.py                 MCP tool (agent-facing)

src/ast_tools/lsp/
  llm_bridge.py                      Thin LSP adapter for codeAction/resolve
```

### Data Flow

```
Agent (Hermes)  
  │  MCP: llm_suggest_fix(code, diagnostic, language)
  ▼
llm_suggest_fix tool
  │  reads LLMConfig from UnifiedConfig
  ▼
LLMClient
  │  1. Build prompt from template + context
  │  2. Try local backend (httpx → Ollama/vLLM, subprocess → llama.cpp)
  │  3. Fall back through remote chain (OpenRouter → Anthropic → Gemini)
  │  4. Parse response as unified diff
  ▼
diff_parser
  │  Validate diff applies cleanly → list of TextEdits
  ▼
Return structured result (success, diff, confidence)

IDE (VS Code)
  │  LSP: codeAction/resolve
  ▼
llm_bridge.py
  │  wraps LLMClient, converts to LSP types
  ▼
code_actions.py
```

---

## Component Specifications

### 1. `llm/client.py` — LLMClient

```python
@dataclass
class LLMFixContext:
    code: str                    # Source code snippet (typically file content)
    diagnostic_message: str      # Human-readable diagnostic (e.g. "Unused import os")
    diagnostic_code: str         # Rule code (e.g. "F401")
    file_path: str               # File path for context
    language: str                # Language ID (python, typescript, etc.)
    context_lines: int = 20      # Lines of context around the issue (default: 20)

@dataclass
class LLMFixResult:
    success: bool
    diff: str | None             # Unified diff string, None if failed
    edits: list[dict] | None     # Parsed TextEdit objects
    model_used: str              # Which model actually generated this
    provider: str                # "local" or "remote"
    confidence: float            # 0.0-1.0 confidence score
    error: str | None            # Error message if failed
    token_usage: dict | None     # {prompt_tokens, completion_tokens, total_tokens}

class LLMClient:
    """Unified LLM interface for generating fix suggestions."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._prompts = Prompts()
    
    async def suggest_fix(self, context: LLMFixContext) -> LLMFixResult:
        """
        1. Build prompt using Prompts.fix_suggestion(context)
        2. Try local backend (if enabled + prefer_local)
        3. Fall back through remote_fallback_chain
        4. Parse response via diff_parser
        5. Compute confidence
        6. Return result
        """
        prompt = self._prompts.fix_suggestion(context)
        
        if self.config.enabled and self.config.prefer_local:
            result = await self._try_local(prompt)
            if result.success:
                return result
        
        for provider in self.config.remote_fallback_chain:
            result = await self._try_remote(prompt, provider)
            if result.success:
                return result
        
        return LLMFixResult(success=False, error="All backends failed", ...)
    
    async def _try_local(self, prompt: str) -> LLMFixResult:
        """Try local backend based on self.config.local_backend."""
        if self.config.local_backend == "ollama":
            return await self._call_ollama(prompt)
        elif self.config.local_backend == "vllm":
            return await self._call_vllm(prompt)
        elif self.config.local_backend == "llama.cpp":
            return await self._call_llamacpp(prompt)
        return LLMFixResult(success=False, error=f"Unknown local backend: {self.config.local_backend}")
    
    async def _try_remote(self, prompt: str, provider: str) -> LLMFixResult:
        """Try remote provider (OpenAI-compatible API)."""
        # Build endpoint from provider mapping
        # Send request with httpx
        # Parse response
        # Return result
        pass
    
    # Backend-specific implementations
    async def _call_ollama(self, prompt: str) -> LLMFixResult: ...
    async def _call_vllm(self, prompt: str) -> LLMFixResult: ...
    async def _call_llamacpp(self, prompt: str) -> LLMFixResult: ...
    async def _call_openai_compat(self, prompt: str, base_url: str, api_key: str, model: str) -> LLMFixResult: ...
```

### 2. `llm/prompts.py` — Structured Prompt Templates

```python
class Prompts:
    """Prompt templates for LLM fix generation."""
    
    @staticmethod
    def fix_suggestion(context: LLMFixContext) -> str:
        """Build the fix suggestion prompt."""
        return (
            "You are an expert code reviewer and fixer. Given a diagnostic and "
            "the surrounding code context, suggest the minimal, correct fix.\n\n"
            f"Diagnostic: {context.diagnostic_message}\n"
            f"Rule: {context.diagnostic_code}\n"
            f"File: {context.file_path}\n"
            f"Language: {context.language}\n"
            "Code context:\n"
            f"```{context.language}\n{context.code}\n```\n\n"
            "Return ONLY the unified diff that fixes the issue. "
            "Use standard unified diff format with lines starting with + and -. "
            "Be minimal — only change what's needed to fix the diagnostic."
        )
    
    @staticmethod
    def code_review(context: LLMFixContext) -> str:
        """Build a code review prompt (future use)."""
        pass
```

### 3. `llm/diff_parser.py` — Diff Validation

```python
def parse_and_validate_diff(
    diff_text: str,
    original_content: str,
    file_extension: str = ".py",
) -> ParseResult:
    """
    Parse a unified diff string and validate it applies cleanly.
    
    Steps:
    1. Parse unified diff header (---/+++ lines) to identify file
    2. Parse hunk headers (@@ line,line @@) to get line ranges
    3. For each hunk:
       a. Extract context lines (prefixed with space)
       b. Verify context lines match original_content
       c. Extract removed lines (-) and added lines (+)
    4. Build list of TextEdit objects from the diff
    5. Apply edits to a copy of original_content
    6. Verify the result is syntactically valid (optional, per language)
    
    Returns:
        ParseResult with parsed edits, confidence, and validation status
    """
    pass

@dataclass
class ParseResult:
    success: bool
    edits: list[dict]              # [{start_line, end_line, new_text}]
    confidence: float              # Based on context match ratio
    error: str | None
    parsed_hunks: int
    matched_hunks: int
    applied_text: str | None       # Full content after applying edits
```

### 4. `llm/__init__.py`

```python
from .client import LLMClient, LLMFixContext, LLMFixResult
from .prompts import Prompts
from .diff_parser import parse_and_validate_diff

__all__ = ["LLMClient", "LLMFixContext", "LLMFixResult", "Prompts", "parse_and_validate_diff"]
```

### 5. `tools/llm_suggest_fix.py` — MCP Tool

```python
def _tool_llm_suggest_fix(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """LLM-assisted fix suggestion.
    
    Uses configured LLM backends (local or remote) to suggest a fix
    for a given code snippet with diagnostic context.
    
    Args:
        code: Source code snippet to fix
        diagnostic: Human-readable diagnostic message
        diagnostic_code: Rule code (e.g., "F401", "E302")
        file_path: Path to the file (for context)
        language: Programming language (python, typescript, etc.)
        context_lines: Lines of context to include (default: 20)
        model: Override model selection (optional)
    
    Returns:
        LLM fix result with diff, confidence, and model info
    """
    pass
```

Registered in `tools/__init__.py` as `llm_suggest_fix`.

### 6. `lsp/llm_bridge.py` — LSP Adapter

```python
class LLMBridge:
    """Connects LSP code action flow to LLMClient."""
    
    def __init__(self, server):
        self.server = server
        self.llm_client = LLMClient(server.config.lsp.llm)
    
    async def resolve_code_action(self, action: lsp_types.CodeAction) -> lsp_types.CodeAction:
        """Resolve a lazy LLM fix action by calling LLMClient."""
        # 1. Extract diagnostic info from action.data
        # 2. Get document content from document_store
        # 3. Call LLMClient.suggest_fix()
        # 4. Convert result to WorkspaceEdit
        # 5. Attach to action.edit
        # 6. Return resolved action
        pass
```

---

## Existing Assets Surveyed

| Asset | Location | Status |
|-------|----------|--------|
| `LLMConfig` | `config/unified.py:149-182` | ✅ Full config: local/remote backends, fallback chain, prompt template |
| `UnifiedConfig.lsp.llm` | `config/unified.py:221` | ✅ LLMConfig nested under LSP config |
| Tool registration pattern | `tools/__init__.py` | ✅ `register_tool(name, handler, schema)` |
| Tool handler pattern | `tools/fix_mcp.py` | ✅ `_tool_*(name, params) -> dict` signature |
| `CodeActionHandler` | `lsp/code_actions.py` | ✅ Wraps fix pipeline, needs LLM bridge |
| `_on_code_action_resolve` | `lsp/server.py:276-281` | ✅ Already wired, delegates to `CodeActionHandler.resolve_code_action()` |

---

## Config Integration

```yaml
# ast-tools.yaml
lsp:
  llm:
    enabled: true
    prefer_local: true
    timeout_seconds: 30
    max_tokens: 2048
    temperature: 0.1
    local_backend: "ollama"      # "ollama", "vllm", "llama.cpp"
    local_host: "127.0.0.1"
    local_port: 11434
    remote_provider: "openrouter"
    remote_model: "qwen/qwen-2.5-coder-32b-instruct"
    remote_fallback_chain:
      - "openrouter"
      - "anthropic"
      - "gemini"
    remote_api_key_env: "OPENROUTER_API_KEY"
```

The LLMClient reads from `config.lsp.llm`. The MCP tool loads config via `UnifiedConfig` (or minimal defaults if not running in LSP context).

---

## Phase Breakdown

| Phase | What | Files | Est. |
|-------|------|-------|------|
| **1** | LLMClient + diff_parser + prompts | 5 files | 4h |
| **2** | MCP tool + CLI flag | 2 files | 2h |
| **3** | LSP bridge + wire into code_actions | 2 files | 2h |
| **4** | Tests for all layers | 5 files | 3h |
| **5** | Audit + lint + documentation | 3 files | 2h |

**Total: 13h**

---

## Audit Synthesis

### Forward Audit — Key Corrections
1. ⚠️ `httpx` NOT in pyproject.toml — must add explicitly
2. ⚠️ Local LLM backends NOT feasible on workstation (4GB RAM, no CUDA) — only remote viable  
3. ✅ All config layer claims verified (LLMConfig, UnifiedConfig.lsp.llm)
4. ✅ Tool registration pattern verified
5. ✅ CodeActionHandler exists and wired in server.py
6. ❌ All `llm/` package files are greenfield

### Reverse Audit — Critical Additions
1. 🔴 **Per-provider API keys** — need separate keys for each provider in fallback chain
2. 🔴 **Retry with backoff** — exponential backoff on 429 / network failures
3. 🔴 **Input truncation** — truncate code context to fit within max_tokens budget
4. 🔴 **Health check** — `LLMClient.is_available()` probes backend before full request
5. 🟠 **Rate limiting** — track 429s, respect Retry-After headers
6. 🟠 **Connect vs read timeouts** — separate configurable timeouts
7. 🟠 **Concurrency semaphore** — max 1 concurrent LLM call (configurable)
8. 🟠 **Prompt injection mitigation** — strip control tokens from code context
9. 🟠 **CLI discoverability** — `ast-tools fix --llm` flag in help

---

## Dependencies

`httpx` is already installed transitively but must be added to `pyproject.toml` explicitly:
```toml
[project.dependencies]
httpx = ">=0.27"
```

No other new packages required.

---

## Acceptance Criteria

- [ ] `llm_suggest_fix` MCP tool returns valid diffs from local LLM
- [ ] `llm_suggest_fix` falls back through remote chain on local failure
- [ ] `diff_parser` validates LLM diffs against original content
- [ ] `diff_parser` rejects diffs that don't apply cleanly
- [ ] LSP `codeAction/resolve` produces WorkspaceEdit from LLM suggestion
- [ ] All 301+ existing tests pass
- [ ] New tests cover: local backend, remote backend, fallback, diff parsing, LSP bridge, MCP tool

---

## Rollback Plan

1. Remove `src/ast_tools/llm/` directory
2. Remove `llm_suggest_fix` from `tools/__init__.py`
3. Remove `llm_bridge.py` from `lsp/`
4. Remove `tests/test_llm/` directory
5. All existing functionality preserved
