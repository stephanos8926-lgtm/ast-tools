# F4 LSP Server — Phase 1 Implementation Plan

**Phase:** 1 of 5 (Core LSP Infrastructure)
**Mode:** MEDIUM
**Duration:** 2 days
**Status:** Ready for sign-off

---

## File Manifest

| File | Description | Lines (est.) |
|------|-------------|--------------|
| `src/ast_tools/lsp/__init__.py` | Package init, exports | 20 |
| `src/ast_tools/lsp/server.py` | Main LanguageServer subclass | 250 |
| `src/ast_tools/lsp/language_router.py` | URI → language → fixers | 100 |
| `src/ast_tools/lsp/diagnostic_publisher.py` | Diagnostics conversion + push | 180 |
| `src/ast_tools/lsp/config_watcher.py` | Config file hot-reload | 120 |
| `src/ast_tools/lsp/document_store.py` | In-memory document sync | 80 |
| `tests/lsp/unit/test_language_router.py` | Language routing tests | 60 |
| `tests/lsp/unit/test_diagnostic_publisher.py` | Diagnostics tests | 80 |
| `tests/lsp/integration/test_lsp_protocol.py` | Full LSP lifecycle tests | 100 |
| `tests/lsp/fixtures/python/simple.py` | Test fixture | 30 |
| `tests/lsp/fixtures/python/with_errors.py` | Error fixture | 30 |
| `tests/lsp/fixtures/workspace/ast-tools.yaml` | Test config | 20 |
| `tests/lsp/fixtures/workspace/pyproject.toml` | Test pyproject | 20 |

**Total: 11 new files, ~1,070 lines**

---

## Component Specifications

### 1. `src/ast_tools/lsp/server.py` — ASTToolsLanguageServer

```python
class ASTToolsLanguageServer(LanguageServer):
    """Main LSP server for ast-tools."""
    
    def __init__(self, *args, **kwargs):
        super().__init__("ast-tools", "0.2.0", *args, **kwargs)
        
        # Core components
        self.config: UnifiedConfig = None
        self.fix_engine: FixEngine = None
        self.language_router: LanguageRouter = None
        self.diagnostic_publisher: DiagnosticPublisher = None
        self.config_watcher: ConfigWatcher = None
        self.document_store: DocumentStore = None
        
        # State
        self._initialized = False
    
    async def initialize(self, params: InitializeParams) -> InitializeResult:
        """Initialize server, load config, setup components."""
        # 1. Load UnifiedConfig from workspace
        # 2. Create LanguageRouter
        # 3. Create FixEngine with plugin_fixers
        # 4. Create DiagnosticPublisher
        # 5. Create DocumentStore
        # 6. Start ConfigWatcher
        # 7. Return capabilities
        pass
    
    async def shutdown(self):
        """Clean shutdown."""
        pass
    
    async def exit(self):
        """Exit handler."""
        pass
```

### 2. `src/ast_tools/lsp/language_router.py` — LanguageRouter

```python
class LanguageRouter:
    """Maps file URIs to languages and fixers."""
    
    EXTENSION_MAP = {
        ".py": "python",
        ".js": "javascript", ".jsx": "javascript",
        ".ts": "typescript", ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", 
        ".c": "c", ".h": "cpp", ".hpp": "cpp",
        ".md": "markdown", ".mdx": "markdown",
    }
    
    def __init__(self, config: UnifiedConfig):
        self.config = config
        self._build_fixer_map()
    
    def _build_fixer_map(self):
        """Build language → fixers map from config."""
        pass
    
    def get_language(self, uri: str) -> str:
        """Map file URI to language ID."""
        pass
    
    def get_fixers_for_language(self, language: str) -> list[FixerBase]:
        """Get all configured fixers for a language (built-in + plugins)."""
        pass
    
    def get_all_languages(self) -> set[str]:
        """Return all supported languages."""
        pass
```

### 3. `src/ast_tools/lsp/diagnostic_publisher.py` — DiagnosticPublisher

```python
class DiagnosticPublisher:
    """Runs fixers in check-only mode, converts to LSP diagnostics."""
    
    def __init__(self, server: ASTToolsLanguageServer):
        self.server = server
        self.config = server.config.lsp.diagnostics
        self._debounce_timers: dict[str, asyncio.Task] = {}
    
    async def publish_diagnostics(self, uri: str, document_text: str, language: str):
        """Run check-only fix pipeline, publish results."""
        # 1. Create FixContext with check_only=True
        # 2. Run fix engine (single iteration, no apply)
        # 3. Convert FixAction → Diagnostic
        # 4. self.server.publish_diagnostics(uri, diagnostics)
        pass
    
    def _fix_actions_to_diagnostics(self, actions: list[FixAction], language: str) -> list[Diagnostic]:
        """Convert FixAction list to LSP Diagnostic objects."""
        pass
    
    def _debounced_publish(self, uri: str, document_text: str, language: str):
        """Debounce rapid changes."""
        pass
```

### 4. `src/ast_tools/lsp/config_watcher.py` — ConfigWatcher

```python
class ConfigWatcher:
    """Watches config files for changes, triggers hot-reload."""
    
    def __init__(self, server: ASTToolsLanguageServer):
        self.server = server
        self._watcher = None
    
    async def start(self):
        """Begin watching config files in workspace folders."""
        pass
    
    async def stop(self):
        """Stop watcher."""
        pass
    
    async def _on_config_change(self, path: Path):
        """Reload config and reinitialize components."""
        pass
```

### 5. `src/ast_tools/lsp/document_store.py` — DocumentStore

```python
class DocumentStore:
    """In-memory document synchronization."""
    
    def __init__(self):
        self._documents: dict[str, TextDocument] = {}
    
    def did_open(self, params: DidOpenTextDocumentParams):
        """Store new document."""
        pass
    
    def did_change(self, params: DidChangeTextDocumentParams):
        """Apply incremental changes."""
        pass
    
    def did_close(self, params: DidCloseTextDocumentParams):
        """Remove document."""
        pass
    
    def get_document(self, uri: str) -> TextDocument | None:
        """Retrieve document by URI."""
        pass
```

---

## Tests

### Unit Tests

```python
# tests/lsp/unit/test_language_router.py
class TestLanguageRouter:
    def test_extension_to_language_mapping(self):
        router = LanguageRouter(...)
        assert router.get_language("file:///test.py") == "python"
        assert router.get_language("file:///test.ts") == "typescript"
        assert router.get_language("file:///test.go") == "go"
        assert router.get_language("file:///test.unknown") == "python"  # default
    
    def test_fixer_map_includes_builtins(self):
        router = LanguageRouter(...)
        python_fixers = router.get_fixers_for_language("python")
        assert any(f.name == "ruff" for f in python_fixers)
    
    def test_fixer_map_includes_plugins(self):
        # Test with custom_fixers config
        pass

# tests/lsp/unit/test_diagnostic_publisher.py
class TestDiagnosticPublisher:
    def test_diagnostic_conversion(self):
        # FixAction → Diagnostic conversion correct
        pass
    
    def test_debounce_prevents_spam(self):
        # Rapid changes debounced
        pass
    
    def test_diagnostic_enrichment(self):
        # code, source, severity, codeDescription present
        pass
```

### Integration Tests

```python
# tests/lsp/integration/test_lsp_protocol.py
class TestLSPProtocol:
    @pytest.mark.asyncio
    async def test_initialize_handshake(self, server):
        result = await server.initialize(InitializeParams(...))
        assert result.capabilities.textDocumentSync.change == 2
        assert result.capabilities.codeActionProvider is not None
        assert result.capabilities.diagnosticProvider is not None
        assert result.capabilities.documentFormattingProvider is not None
    
    @pytest.mark.asyncio
    async def test_did_open_publishes_diagnostics(self, server):
        await server.initialize(...)
        await server.did_open(DidOpenTextDocumentParams(...))
        # Wait for diagnostics
        diagnostics = await server.wait_for_diagnostics("file:///test.py")
        assert len(diagnostics) > 0
    
    @pytest.mark.asyncio
    async def test_did_change_updates_diagnostics(self, server):
        # Edit file → diagnostics update (debounced)
        pass
    
    @pytest.mark.asyncio
    async def test_did_save_triggers_fix(self, server):
        # Save with fix_on_save=true → fixes applied
        pass
```

---

## Dependencies

### New Dependencies (add to `pyproject.toml`)

```toml
[project.optional-dependencies]
lsp = [
    "pygls>=2.1.0",
    "lsprotocol>=2024.0.0",
    "watchdog>=4.0.0",  # for config watching
]
```

### Internal Dependencies

| Component | Depends On |
|-----------|------------|
| `server.py` | `language_router.py`, `diagnostic_publisher.py`, `config_watcher.py`, `document_store.py` |
| `language_router.py` | `UnifiedConfig`, `get_fixer_for_language`, `register_plugin_fixers` |
| `diagnostic_publisher.py` | `FixEngine`, `FixContext`, `FixAction`, `Diagnostic` (lsprotocol) |
| `config_watcher.py` | `watchdog`, `UnifiedConfig`, `load_unified_config` |
| `document_store.py` | `lsprotocol.types` |

---

## Configuration Integration

The server loads config via:
```python
from ast_tools.config.unified import load_unified_config, UnifiedConfig

# In server.initialize():
self.config = load_unified_config(
    pyproject_path=workspace_root / "pyproject.toml",
    yaml_path=workspace_root / "ast-tools.yaml",
    cli_overrides={"lsp": {"enabled": True}}
)
```

---

## CLI Entry Point

Add to `src/ast_tools/cli.py`:

```python
def cmd_lsp(args: argparse.Namespace) -> int:
    """Start LSP server."""
    from ast_tools.lsp.server import ASTToolsLanguageServer
    import sys
    
    server = ASTToolsLanguageServer()
    server.start_io()  # stdio transport
    return 0

# In argument parser:
lsp_parser = subparsers.add_parser("lsp", help="Start LSP server")
lsp_parser.set_defaults(func=cmd_lsp)
```

---

## Acceptance Criteria

- [ ] `ast-tools lsp` starts without errors
- [ ] `initialize` returns correct capabilities
- [ ] Opening Python file triggers Ruff diagnostics
- [ ] Editing file updates diagnostics (debounced 300ms)
- [ ] Saving file runs fix pipeline (if `fix_on_save: true`)
- [ ] Config change in `ast-tools.yaml` hot-reloads
- [ ] Custom fixer plugin loaded via config works
- [ ] All 255 existing tests pass
- [ ] New LSP unit tests pass
- [ ] New LSP integration tests pass

---

## Rollback Plan

If issues arise:
1. Revert `cli.py` LSP command
2. Remove `src/ast_tools/lsp/` directory
3. Remove `lsp` extra from `pyproject.toml`
4. All existing functionality preserved

---

## Sign-Off Required

**Before implementation begins, user must approve:**
- [ ] File manifest correct
- [ ] Component specs aligned with spec document
- [ ] Dependencies acceptable
- [ ] Test strategy sufficient
- [ ] Rollback plan adequate