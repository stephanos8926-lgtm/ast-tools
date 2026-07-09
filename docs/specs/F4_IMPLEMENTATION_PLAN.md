# F4 LSP Server — MEDIUM Mode Implementation Plan

**Mode:** MEDIUM (default for new capabilities — 5+ files, MCP/LSP integration, reusable feature)
**Created:** 2026-07-09
**Author:** Lucien
**Based on:** plan-and-audit skill v2.0.0

---

## Phase 0: Research — COMPLETED ✅

Research already completed and documented in:
- `docs/specs/F4_LSP_SERVER_SPEC.md` — Full specification with competitive analysis
- `docs/specs/F4_PHASE1_LSP_CORE.md` through `F4_PHASE5_POLISH_RELEASE.md` — Phase documents

**Key findings from competitive analysis:**
- pygls is the right framework (used by Ruff, Python LSP)
- Ruff LSP: async-free, blocking handlers on main thread, snapshot testing
- Biome: lazy `codeAction/resolve`, multi-root workspace, lsp-proxy daemon
- rust-analyzer: AnalysisHost/Analysis with explicit cancellation
- efm-langserver: generic wrapper pattern (validates our approach)
- Multi-language LSP servers (lsp-mcp, agent-lsp) validate unified server model

---

## Phase 1: Specification — COMPLETED ✅

**Document:** `docs/specs/F4_LSP_SERVER_SPEC.md`

**Spec includes:**
- Server capabilities (initialize response)
- Supported LSP methods (12 methods)
- Code action design (7 action kinds)
- Diagnostics sources and enrichment
- Configuration schema (nested LSPConfig with Diagnostic/Formatting/LLM configs)
- Language routing table
- LLM integration (local + remote unified client)
- Performance targets
- Testing strategy
- Distribution plan

---

## Phase 2: Implementation Plan — THIS DOCUMENT

### 2.1 File Manifest

| Phase | Files | Est. Lines | Description |
|-------|-------|------------|-------------|
| **Phase 1** | 7 files | ~1,500 | Core LSP infrastructure |
| **Phase 2** | 5 files | ~1,200 | Code actions & LLM integration |
| **Phase 3** | 3 files | ~600 | Semantic features (hover, goto, refs) |
| **Phase 4** | 3 files | ~500 | Config hot-reload, CLI, tests |
| **Phase 5** | 5 files | ~800 | CI/CD, docs, packaging, release |

**Total: ~23 files, ~4,600 lines**

### 2.2 Phase 1: Core LSP Infrastructure (Days 1-2)

#### Files to Create

1. **`src/ast_tools/lsp/__init__.py`** — Package exports
2. **`src/ast_tools/lsp/server.py`** — Main server class (400 lines)
3. **`src/ast_tools/lsp/language_router.py`** — Language → fixer mapping (150 lines)
4. **`src/ast_tools/lsp/diagnostic_publisher.py`** — Diagnostics (250 lines)
5. **`src/ast_tools/lsp/config_watcher.py`** — Hot reload (200 lines)
5. **`src/ast_tools/lsp/document_store.py`** — Document sync (200 lines)
6. **`src/ast_tools/lsp/cli.py`** — `ast lsp` command (100 lines)
7. **`src/ast_tools/lsp/capabilities.py`** — Server capabilities (50 lines)

#### Key Classes

```python
# server.py
class ASTToolsLanguageServer(LanguageServer):
    def __init__(self):
        super().__init__("ast-tools", "0.2.0")
        self.config: UnifiedConfig = None
        self.fix_engine: FixEngine = None
        self.language_router: LanguageRouter = None
        self.diagnostic_publisher: DiagnosticPublisher = None
        self.config_watcher: ConfigWatcher = None
        self.document_store: DocumentStore = None
        self._initialized = False
    
    async def initialize(self, params: InitializeParams) -> InitializeResult:
        # Load config, init components, register capabilities
        pass
    
    async def shutdown(self):
        # Cleanup
        pass

# language_router.py
class LanguageRouter:
    EXTENSION_MAP = {".py": "python", ...}
    
    def get_language(self, uri: str) -> str: ...
    def get_fixers_for_language(self, language: str, config: UnifiedConfig): ...

# diagnostic_publisher.py
class DiagnosticPublisher:
    def __init__(self, server, config: DiagnosticConfig): ...
    async def publish_diagnostics(self, uri: str, text: str, language: str): ...
    def _fix_actions_to_diagnostics(self, actions: list[FixAction]) -> list[Diagnostic]: ...

# config_watcher.py
class ConfigWatcher:
    def __init__(self, server): ...
    async def start(self): ...  # Watch config files in workspace folders
    async def on_config_change(self, path: Path): ...

# document_store.py
class DocumentStore:
    def __init__(self): self._docs: dict[str, TextDocument] = {}
    def get(self, uri: str) -> str: ...
    def update(self, uri: str, text: str): ...
    def remove(self, uri: str): ...
```

### 2.3 Phase 2: Code Actions & LLM Integration (Days 3-5)

#### Files to Create

1. **`src/ast_tools/lsp/code_actions.py`** — Code action handler (350 lines)
2. **`src/ast_tools/lsp/fix_action_builder.py`** — FixAction → CodeAction (150 lines)
3. **`src/ast_tools/lsp/llm_client.py`** — Unified LLM client (300 lines)
4. **`src/ast_tools/lsp/diff_parser.py`** — Diff validation (100 lines)
5. **`src/ast_tools/lsp/llm_backends.py`** — Local/remote backends (300 lines)

#### Key Classes

```python
# code_actions.py
class CodeActionHandler:
    def __init__(self, server): ...
    async def code_action(self, params: CodeActionParams) -> list[CodeAction]:
        # 1. Get document, language, range
        # 2. Run fixers in check-only mode for range
        # 3. Build quickfix actions per diagnostic
        # 4. Build source.fixAll (lazy)
        # 5. Build source.organizeImports
        # 6. Build refactor actions
        # 7. Build LLM fix action (if enabled)
        pass
    
    async def code_action_resolve(self, action: CodeAction) -> CodeAction:
        # Lazy compute WorkspaceEdit for fixAll, LLM fix
        pass

# llm_client.py
class LLMClient:
    def __init__(self, config: LLMConfig): ...
    async def is_available(self) -> bool: ...
    async def suggest_fix(self, context: LLMFixContext) -> LLMFixResult:
        # 1. Build prompt
        # 2. Try local first if prefer_local
        # 3. Fallback through remote chain
        # 4. Parse diff, validate
        pass

# llm_backends.py
class LlamaCppBackend:
    async def generate(self, prompt: str) -> str: ...

class OllamaBackend:
    async def generate(self, prompt: str) -> str: ...

class OpenRouterBackend:
    async def generate(self, prompt: str) -> str: ...

class AnthropicBackend:
    async def generate(self, prompt: str) -> str: ...

class GeminiBackend:
    async def generate(self, prompt: str) -> str: ...
```

### 2.4 Phase 3: Semantic Features (Days 6-7)

#### Files to Create

1. **`src/ast_tools/lsp/semantic.py`** — Hover, goto definition, references (300 lines)
2. **`src/ast_tools/lsp/symbols.py`** — Document/workspace symbols (200 lines)
3. **`src/ast_tools/lsp/formatting.py`** — Formatting/range formatting (100 lines)

#### Key Methods

```python
# semantic.py
async def hover(self, params: HoverParams) -> Hover:
    # Use ast_tools hover + semantic search
    pass

async def definition(self, params: DefinitionParams) -> Location | list[Location]:
    # Use ast_tools find_symbol_definition
    pass

async def references(self, params: ReferenceParams) -> list[Location]:
    # Use ast_tools find_references
    pass

# symbols.py
async def document_symbol(self, params: DocumentSymbolParams) -> list[DocumentSymbol]:
    # Use ast_tools list_symbols
    pass

async def workspace_symbol(self, params: WorkspaceSymbolParams) -> list[SymbolInformation]:
    # Use ast_tools semantic_search
    pass

# formatting.py
async def formatting(self, params: DocumentFormattingParams) -> list[TextEdit]:
    # Run fix pipeline on entire document
    pass

async def range_formatting(self, params: DocumentRangeFormattingParams) -> list[TextEdit]:
    # Run fix pipeline on range
    pass
```

### 2.5 Phase 4: Config, CLI, Tests (Days 8-9)

#### Files to Create/Modify

1. **`src/ast_tools/cli.py`** — Add `cmd_lsp` function (50 lines)
2. **`src/ast_tools/lsp/tests/test_lsp_integration.py`** — Integration tests (300 lines)
3. **`src/ast_tools/lsp/tests/test_code_actions.py`** — Code action tests (200 lines)
4. **`src/ast_tools/lsp/tests/test_llm_client.py`** — LLM client tests (150 lines)
5. **`tests/fixtures/lsp_test_project/`** — Test project fixture

#### Test Matrix

| Test | Description |
|------|-------------|
| `test_lsp_initialize` | Handshake returns correct capabilities |
| `test_lsp_did_open` | Opening file triggers diagnostic publish |
| `test_lsp_did_change` | Changes debounced, diagnostics updated |
| `test_lsp_did_save` | Save triggers fix pipeline if configured |
| `test_code_action_quickfix` | Single diagnostic → quickfix action with edit |
| `test_code_action_fix_all` | fixAll action returns lazy action, resolve computes edit |
| `test_code_action_organize_imports` | Organize imports action works |
| `test_code_action_llm_fix` | LLM fix action appears when enabled + available |
| `test_code_action_resolve` | Resolve computes full WorkspaceEdit |
| `test_language_router` | Extension → language → fixers mapping |
| `test_config_hot_reload` | Config change reloads without restart |
| `test_formatting` | Document formatting uses fix pipeline |
| `test_semantic_features` | Hover, goto def, refs work |
| `test_custom_fixer_plugin` | Plugin fixers loaded and used |

### 2.6 Phase 5: CI/CD, Docs, Release (Day 10)

#### Files to Create

1. **`.github/workflows/lsp.yml`** — CI for LSP
2. **`.github/workflows/release.yml`** — Release automation
3. **`Dockerfile.lsp`** — Docker image
4. **`docs/lsp/*.md`** — 10 documentation files
5. **`examples/ast-tools.yaml`** — Example config
6. **`packages/vscode-ast-tools/`** — VS Code extension (separate repo recommended)

---

## Phase 3: Forward Audit — REQUIRED

**Scope:** Validate spec claims against actual codebase capabilities

**Audit Questions:**
1. Can current `FixEngine` run in check-only mode for diagnostics? ✅ Yes (`check_only` param)
2. Can `FixEngine` accept custom plugin fixers? ✅ Yes (`plugin_fixers` param)
3. Does `UnifiedConfig` have all LSP/LLM fields? ✅ Yes (just added)
4. Can `ast_tools` semantic search be called synchronously? Need to verify
5. Does `pygls` support `codeAction/resolve`? Yes (standard LSP 3.16+)
6. Can we run LLM inference without blocking LSP main thread? Need async pattern
7. Does `textDocument/diagnostic` (pull) work with pygls? Yes

**Risks Identified:**
- **Async LLM calls in codeAction**: Must not block LSP thread. Use `asyncio.create_task` with timeout.
- **Config precedence**: LSP `didChangeConfiguration` must override file config
- **Multi-root workspace**: Each folder may have different config
- **Large file handling**: `max_file_size` config must be respected

---

## Phase 4: Reverse Audit — REQUIRED

**Scope:** Find gaps in spec vs. implementation needs

**Checklist:**
- [ ] LSP initialization sequence documented
- [ ] Error handling for missing fixers
- [ ] Diagnostic deduplication (same issue from multiple fixers)
- [ ] Workspace edit conflict resolution (multiple fixers editing same range)
- [ ] LLM prompt template variable injection safety
- [ ] Local model auto-download on first use
- [ ] Telemetry/opt-out for LLM usage
- [ ] Fallback when all LLM backends fail
- [ ] Graceful degradation if pygls not installed

---

## Phase 5: Synthesis & Sign-off

**Synthesis Document:** Will be created after audits complete
**Sign-off Required:** User must approve before TDD implementation

---

## Phase 6-11: TDD Implementation + Audits (MEDIUM Mode)

Per plan-and-audit skill, MEDIUM mode requires:
- Phase 7: TDD Implement (tests first)
- Phase 8: Adversarial Audit (security + edge cases)
- Phase 9: Bug Review (logic, security, quality)
- Phase 10: Lint + Dead Code
- Phase 11: Test/Perf/Sec Documentation

**Parallel Execution:** Phases 3+4 (semantic + formatting) can run in parallel with Phase 2 (code actions) since they touch different files.

---

## Timeline Summary

| Week | Phase | Focus |
|------|-------|-------|
| Day 1-2 | Phase 1 | Core LSP server, document sync, diagnostics |
| Day 3-5 | Phase 2 | Code actions, fix pipeline, LLM integration |
| Day 6-7 | Phase 3 | Semantic features, formatting |
| Day 8-9 | Phase 4 | CLI, tests, config hot-reload |
| Day 10 | Phase 5 | CI/CD, docs, release, Docker |

**Total: 10 working days**

---

## Resource Requirements

- **pygls** — Already in dependencies? Need to verify
- **lsprotocol** — LSP types
- **llama-cpp-python** — Optional, for local LLM
- **httpx** — For remote LLM calls
- **watchdog** — Config file watching (optional, can use pygls built-in)

---

## Next Steps

1. **Forward Audit** — Validate spec against current codebase
2. **Reverse Audit** — Identify implementation gaps
3. **Synthesis** — Final refined plan
4. **Sign-off** — User approval
5. **Implementation** — Begin Phase 1