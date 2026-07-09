# ast-tools LSP Server — Specification

**Version:** 1.0
**Status:** Draft — pending forward/reverse audit
**Author:** Lucien
**Date:** 2026-07-09

---

## 1. Overview

The `ast-tools-lsp` server is a Language Server Protocol (LSP) implementation that exposes the `ast-tools` unified fix pipeline, semantic analysis, and LLM-assisted fix refinement as editor-integrated features. It serves as the single LSP entry point for all languages supported by `ast-tools` (Python, TypeScript/JavaScript, Go, Rust, C/C++, Markdown, and custom plugin languages).

### 1.1 Goals

1. **Unified Fix Actions**: Single `textDocument/codeAction` endpoint that orchestrates all configured fixers (built-in + plugins) for the target file's language.
2. **Real-time Diagnostics**: Push diagnostics from all active fixers via `textDocument/publishDiagnostics`.
3. **Formatting**: `textDocument/formatting` and `textDocument/rangeFormatting` via the fix pipeline.
4. **Configuration Integration**: Read `ast-tools.yaml` / `pyproject.toml` for project-specific fixer settings, safety levels, and custom plugins.
5. **LLM-Assisted Refinement**: Optional integration with local (llama.cpp/Ollama) and remote (OpenRouter/Anthropic/Gemini) LLMs for complex fix suggestions.
6. **Multi-language Support**: Single server instance routes requests to language-appropriate fixers based on file extension / LSP language ID.

### 1.2 Non-Goals

- Full language server features (completion, hover, go-to-definition) — these exist as MCP tools.
- Replacing language-specific LSPs (rust-analyzer, gopls, pylsp) — we complement them with cross-language fix orchestration.
- Cloud-based agent execution — all fixes run locally.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ast-tools-lsp                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  pygls       │  │  FixEngine   │  │  LLMClient           │  │
│  │  (LSP proto) │──▶│  (orchestr.) │──▶│  (local + remote)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│         │                │                     │                │
│         ▼                ▼                     ▼                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              UnifiedConfig (ast-tools.yaml)              │  │
│  │  fix: {safety, max_iterations, custom_fixers: {...}}     │  │
│  │  llm: {enabled, prefer_local, local: {...}, remote: {...}}│  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `pygls` server | LSP protocol handling, JSON-RPC, document sync |
| `LanguageRouter` | Maps file URI → language → fixer set |
| `FixEngine` | Runs configured fixers, returns `FixAction` list |
| `DiagnosticPublisher` | Converts `FixAction` + lint results → LSP `Diagnostic` |
| `LLMClient` | Unified interface for local/remote LLM fix suggestions |
| `ConfigWatcher` | Watches `ast-tools.yaml` / `pyproject.toml` for hot-reload |

---

## 3. LSP Capabilities

### 3.1 Server Capabilities (initialize response)

```json
{
  "capabilities": {
    "textDocumentSync": {
      "openClose": true,
      "change": 2,           // Incremental
      "willSave": false,
      "willSaveWaitUntil": false,
      "save": {"includeText": true}
    },
    "codeActionProvider": {
      "codeActionKinds": [
        "quickfix",
        "source.fixAll",
        "source.organizeImports",
        "refactor.extract",
        "refactor.inline",
        "ast-tools.llmFix"
      ],
      "resolveProvider": true
    },
    "diagnosticProvider": {
      "interFileDependencies": true,
      "workspaceDiagnostics": true
    },
    "documentFormattingProvider": true,
    "documentRangeFormattingProvider": true,
    "workspace": {
      "workspaceFolders": {"supported": true, "changeNotifications": true}
    }
  }
}
```

### 3.2 Supported Methods

| Method | Implementation |
|--------|----------------|
| `initialize` / `initialized` | Version negotiation, capability advertisement, config load |
| `textDocument/didOpen` | Register document, trigger initial diagnostic publish |
| `textDocument/didChange` | Update document, debounced re-diagnose |
| `textDocument/didSave` | Run fix pipeline if `fixOnSave` configured |
| `textDocument/codeAction` | **Core** — return unified fix actions + LLM refine |
| `codeAction/resolve` | Lazy computation of `WorkspaceEdit` for large fixes |
| `textDocument/publishDiagnostics` | Push diagnostics from all fixers |
| `textDocument/diagnostic` | Pull diagnostics (alternative to push) |
| `textDocument/formatting` | Full document format via fix pipeline |
| `textDocument/rangeFormatting` | Range format via fix pipeline |
| `workspace/didChangeConfiguration` | Hot-reload `ast-tools.yaml` settings |
| `workspace/didChangeWatchedFiles` | Config file change detection |
| `shutdown` / `exit` | Cleanup |

---

## 4. Code Action Design

### 4.1 Action Kinds & Sources

| Kind | Source | Description |
|------|--------|-------------|
| `quickfix` | Individual fixers | Single diagnostic fix (e.g., "Remove unused import") |
| `source.fixAll` | FixEngine | Apply all safe fixes from all configured fixers |
| `source.fixAll.unsafe` | FixEngine | Apply all fixes including unsafe (opt-in) |
| `source.organizeImports` | Language fixers | Organize imports (Ruff, ESLint, goimports) |
| `refactor.extract` | ast-tools semantic | Extract interface, function, variable |
| `refactor.inline` | ast-tools semantic | Inline function, variable |
| `ast-tools.llmFix` | LLMClient | AI-suggested fix for complex diagnostics |

### 4.2 CodeAction Structure

```python
# Minimal CodeAction for quickfix (immediate)
CodeAction(
    title="Remove unused import 'os'",
    kind=CodeActionKind.QuickFix,
    diagnostics=[diagnostic],  # linked diagnostic
    edit=WorkspaceEdit(changes={uri: [TextEdit]}),
    is_preferred=True
)

# FixAll action (lazy via resolve)
CodeAction(
    title="ast-tools: Fix all issues (safe)",
    kind=CodeActionKind.SourceFixAll,
    diagnostics=all_diagnostics,
    # NO edit here — computed on resolve
    data={"action_type": "fix_all", "safety": "safe", "uri": uri}
)

# LLM Fix action
CodeAction(
    title="🤖 AI: Suggest fix for 'complex issue'",
    kind=CodeActionKind.Refactor,  # custom: "ast-tools.llmFix"
    diagnostics=[diagnostic],
    data={"action_type": "llm_fix", "diagnostic_code": "E123", "uri": uri}
)
```

### 4.3 Lazy Resolution (`codeAction/resolve`)

For `source.fixAll` and `ast-tools.llmFix` actions on large files:

1. Initial `codeAction` returns `CodeAction` **without** `edit` field
2. Includes `data` payload with action metadata
3. Client calls `codeAction/resolve` when user selects action
4. Server computes full `WorkspaceEdit` and returns complete `CodeAction`

---

## 5. Diagnostics

### 5.1 Sources

| Source | Diagnostic Codes | Severity |
|--------|------------------|----------|
| Ruff (Python) | `E***`, `W***`, `F***`, `I***`, `C***`, `N***`, `D***`, `UP***`, `PTH***`, `FLY***`, `T20*`, `ERA***`, `PD***`, `PGH***`, `PIE***`, `PL***`, `TRY***`, `NPY***`, `RUF***`, `SIM***`, `TID***`, `ARG***`, `PTH***` | Error/Warning/Info |
| ESLint (TS/JS) | `eslint(*)` | Error/Warning |
| goimports/golangci-lint (Go) | `go/*` | Error/Warning |
| rustfmt/clippy (Rust) | `rust/*` | Error/Warning |
| clang-format/tidy (C/C++) | `clang/*` | Error/Warning |
| Prettier (Markdown) | `prettier/*` | Warning |
| Custom plugins | `plugin.<name>/*` | Configurable |
| LLM suggestions | `llm/*` | Info/Hint |

### 5.2 Diagnostic Enrichment

Each diagnostic includes:
- `code` — rule identifier
- `source` — "ast-tools.ruff", "ast-tools.eslint", etc.
- `message` — human-readable
- `range` — LSP Range
- `severity` — Error/Warning/Information/Hint
- `tags` — [Unnecessary, Deprecated] if applicable
- `codeDescription` — URI to rule documentation
- `data` — `{ "fixable": true, "fixer": "ruff", "safety": "safe" }` for quickfix linking

---

## 6. Configuration

### 6.1 `ast-tools.yaml` / `pyproject.toml [tool.ast-tools]`

```yaml
# Fix pipeline configuration
fix:
  enabled: true
  safety_level: "safe"              # "safe" | "unsafe" | "display_only"
  max_iterations: 10
  check_only: false
  fix_on_save: true                 # Run fix pipeline on textDocument/didSave
  format_on_save: true              # Run formatter on save
  custom_fixers:                    # Plugin fixers (module:Class)
    sql: "my_project.fixers:SQLFixer"
    yaml: "my_project.fixers:YAMLFixer"

# LSP-specific settings
lsp:
  enabled: true
  host: "127.0.0.1"
  port: 2087                        # stdio if not set
  diagnostics:
    enabled: true
    debounce_ms: 300                # Debounce didChange → publishDiagnostics
    max_diagnostics_per_file: 100
    pull_diagnostics: false         # Use textDocument/diagnostic instead of push
  code_actions:
    resolve_timeout_ms: 5000        # Timeout for codeAction/resolve
    include_unsafe_fixall: false    # Show "Fix All (unsafe)" action
    include_llm_fix: true           # Show AI fix actions
  formatting:
    enabled: true
    range_formatting: true

# LLM configuration for fix refinement
llm:
  enabled: true
  prefer_local: true
  timeout_seconds: 30
  max_tokens: 2048
  temperature: 0.1
  local:
    backend: "llama.cpp"            # "llama.cpp" | "ollama" | "vllm"
    model_path: "~/.cache/ast-tools/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    n_gpu_layers: -1                # -1 = all, 0 = CPU only
    n_ctx: 8192
  remote:
    provider: "openrouter"          # "openrouter" | "anthropic" | "gemini"
    model: "qwen/qwen-2.5-coder-32b-instruct"
    fallback_chain:
      - "openrouter"
      - "anthropic"
      - "gemini"
    api_key_env: "OPENROUTER_API_KEY"  # or ANTHROPIC_API_KEY, GEMINI_API_KEY
  prompt_template: |
    You are an expert code fixer. Given a diagnostic and code context,
    suggest a minimal, correct fix. Return only the unified diff.
    
    Diagnostic: {diagnostic_message}
    Rule: {diagnostic_code}
    File: {file_path}
    Language: {language}
    Code context:
    {code_context}
    
    Fix:
```

### 6.2 Configuration Precedence

1. Defaults (hardcoded in `UnifiedConfig`)
2. `pyproject.toml` `[tool.ast-tools]`
3. `~/.config/ast-tools/ast-tools.yaml`
4. Project-root `ast-tools.yaml`
5. LSP `workspace/didChangeConfiguration` (runtime override)
6. CLI flags (if running via `ast-tools lsp` command)

---

## 7. LLM Integration

### 7.1 Unified Client Interface

```python
class LLMClient:
    """Unified interface for local + remote LLM fix suggestions."""
    
    async def suggest_fix(self, context: LLMFixContext) -> LLMFixResult:
        """
        1. Build prompt from context (diagnostic + code + AST info)
        2. Try local backend first if enabled + available
        3. Fall back through remote chain on failure
        4. Parse response as unified diff
        5. Validate diff applies cleanly
        6. Return structured result with confidence
        """
        pass
    
    async def is_available(self) -> bool:
        """Check if any backend is responsive."""
        pass

@dataclass
class LLMFixContext:
    diagnostic: Diagnostic
    code_context: str           # ~100 lines around diagnostic
    file_path: Path
    language: str
    ast_context: str | None     # Optional: semantic info from ast-tools

@dataclass
class LLMFixResult:
    success: bool
    diff: str | None            # Unified diff
    confidence: float           # 0.0 - 1.0
    model_used: str
    error: str | None
```

### 7.2 Local Backends

| Backend | Command / Library | Models |
|---------|-------------------|--------|
| `llama.cpp` | `llama-cpp-python` | GGUF (Qwen, CodeLlama, DeepSeek-Coder) |
| `Ollama` | HTTP `/api/generate` | Any Ollama model |
| `vLLM` | OpenAI-compat HTTP | Any HF model |

### 7.3 Remote Providers

| Provider | API Format | Auth |
|----------|------------|------|
| OpenRouter | OpenAI-compat | `OPENROUTER_API_KEY` |
| Anthropic | Anthropic API | `ANTHROPIC_API_KEY` |
| Gemini | Google AI API | `GEMINI_API_KEY` |

---

## 8. Language Routing

### 8.1 File Extension → Language → Fixers

| Extension | Language ID | Fixers |
|-----------|-------------|--------|
| `.py` | `python` | Ruff |
| `.js`, `.jsx` | `javascript` | ESLint + Prettier |
| `.ts`, `.tsx` | `typescript` | ESLint + Prettier |
| `.go` | `go` | goimports + golangci-lint |
| `.rs` | `rust` | rustfmt + clippy |
| `.cpp`, `.cc`, `.cxx`, `.c`, `.h`, `.hpp` | `cpp` | clang-format + clang-tidy |
| `.md`, `.mdx` | `markdown` | Prettier |
| Custom | Via plugin | Custom fixer |

### 8.2 Plugin Language Registration

```python
# In custom_fixers config:
custom_fixers:
  sql: "my_project.fixers:SQLFixer"
  # SQLFixer must declare:
  #   supported_languages = ["sql"]
  #   file_extensions = [".sql"]
```

The `LanguageRouter` dynamically builds the map from:
1. Built-in fixers
2. `custom_fixers` config (loads plugin, reads `supported_languages`)

---

## 9. Performance Requirements

| Metric | Target |
|--------|--------|
| `initialize` response | < 500ms |
| `textDocument/codeAction` (quickfix) | < 200ms |
| `textDocument/codeAction` (fixAll) | < 1s (lazy resolve) |
| `textDocument/diagnostic` (pull) | < 500ms |
| Diagnostics debounce | 300ms (configurable) |
| Memory (idle) | < 150MB |
| Memory (active, large workspace) | < 500MB |
| Startup (cold, no index) | < 3s |

---

## 10. Testing Strategy

### 10.1 Unit Tests

- `LanguageRouter` mapping correctness
- `DiagnosticPublisher` conversion accuracy
- `LLMClient` local/remote fallback logic
- Config loading precedence

### 10.2 Integration Tests (LSP Protocol)

- `initialize` handshake
- `didOpen` → `publishDiagnostics` flow
- `codeAction` returns expected actions
- `codeAction/resolve` computes correct edits
- `formatting` applies fixes
- Config hot-reload on `didChangeConfiguration`

### 10.3 Fixture-Based Tests

- Per-language test fixtures with known diagnostics/fixes
- Multi-language workspace test
- Custom fixer plugin test
- LLM fix suggestion test (mocked)

---

## 11. Distribution

### 11.1 Installation

```bash
# Via pip (includes pygls, lsprotocol, llama-cpp-python optional)
pip install ast-tools[lsp]

# Or with all LLM backends
pip install ast-tools[lsp,llm-local,llm-remote]
```

### 11.2 Editor Integration

**VS Code** (`package.json`):
```json
{
  "name": "ast-tools",
  "publisher": "rapidwebs",
  "engines": {"vscode": "^1.80.0"},
  "categories": ["Linters", "Formatters"],
  "activationEvents": ["onLanguage:python", "onLanguage:typescript", "..."],
  "main": "./out/extension.js",
  "contributes": {
    "configuration": {
      "type": "object",
      "title": "ast-tools",
      "properties": {
        "ast-tools.enable": {"type": "boolean", "default": true},
        "ast-tools.configPath": {"type": "string", "default": ""}
      }
    }
  }
}
```

**Neovim** (`nvim-lspconfig`):
```lua
require'lspconfig'.ast_tools.setup{
  cmd = {'ast-tools', 'lsp'},
  filetypes = {'python', 'typescript', 'javascript', 'go', 'rust', 'cpp', 'markdown'},
  root_dir = require'lspconfig'.util.root_pattern('ast-tools.yaml', 'pyproject.toml', '.git'),
}
```

---

## 12. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| pygls async complexity | Medium | High | Follow ruff-analyzer pattern: synchronous handlers on main thread, background for heavy work |
| LLM latency in codeAction | Medium | Medium | Lazy resolve; timeout; cache suggestions |
| Config schema drift | Low | Medium | UnifiedConfig single source; validation on load |
| Multi-language file conflicts | Low | Low | LanguageRouter isolates per file; no cross-file state |
| Custom plugin crashes | Medium | Medium | Sandbox plugin execution; timeout; graceful degradation |

---

## 13. Acceptance Criteria

1. ✅ `ast-tools lsp` starts and responds to `initialize`
2. ✅ Opening a Python file shows Ruff diagnostics in editor
3. ✅ Clicking 💡 on diagnostic shows "Quick fix" + "ast-tools: Fix all"
4. ✅ "Fix all" applies Ruff + Prettier + custom fixers in one action
5. ✅ Saving file runs fix pipeline (if `fix_on_save: true`)
6. ✅ Formatting via editor (Shift+Alt+F) uses fix pipeline
7. ✅ Custom plugin fixer registered via config appears in actions
8. ✅ LLM fix action appears when enabled + backend available
9. ✅ Config changes hot-reload without server restart
10. ✅ All unit + integration tests pass