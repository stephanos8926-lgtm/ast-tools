# F4 LSP Server — Phase 1: Core LSP Infrastructure

**Phase:** 1 of 5
**Duration:** 2 days
**Dependencies:** F1, F2, F3 complete (✅)
**Status:** Ready to implement

---

## Scope

Build the foundational LSP server using `pygls` that can:
- Initialize and respond to LSP handshake
- Handle document synchronization (open, change, close, save)
- Load and expose `UnifiedConfig` (including new LSP/LLM sections)
- Route requests to language-appropriate fixers
- Publish diagnostics via push model

---

## Deliverables

### 1. `src/ast_tools/lsp/server.py` — Main LSP Server
```python
class ASTToolsLanguageServer(LanguageServer):
    """Main LSP server for ast-tools."""
    
    def __init__(self):
        super().__init__("ast-tools", "0.2.0")
        self.config: UnifiedConfig = None
        self.fix_engine: FixEngine = None
        self.language_router: LanguageRouter = None
        self.diagnostic_publisher: DiagnosticPublisher = None
        self.config_watcher: ConfigWatcher = None
```

### 2. `src/ast_tools/lsp/language_router.py` — Language → Fixer Mapping
```python
class LanguageRouter:
    """Routes LSP requests to language-appropriate fixers."""
    
    EXTENSION_MAP = {
        ".py": "python",
        ".js": "javascript", ".jsx": "javascript",
        ".ts": "typescript", ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".c": "c", ".h": "cpp", ".hpp": "cpp",
        ".md": "markdown", ".mdx": "markdown",
    }
    
    def get_language(self, uri: str) -> str:
        """Map file URI to language ID."""
        pass
    
    def get_fixers_for_language(self, language: str, config: UnifiedConfig) -> list[FixerBase]:
        """Get all configured fixers for a language (built-in + plugins)."""
        pass
```

### 3. `src/ast_tools/lsp/diagnostic_publisher.py` — Diagnostics
```python
class DiagnosticPublisher:
    """Converts fixer results to LSP diagnostics and publishes them."""
    
    def __init__(self, server: ASTToolsLanguageServer, config: DiagnosticConfig):
        self.server = server
        self.config = config
        self._debounce_timers: dict[str, Timer] = {}
    
    async def publish_diagnostics(self, uri: str, document_text: str, language: str):
        """Run fixers in check-only mode, convert to LSP diagnostics."""
        pass
    
    def _fix_actions_to_diagnostics(self, actions: list[FixAction], language: str) -> list[Diagnostic]:
        """Convert FixAction list to LSP Diagnostic objects."""
        pass
```

### 4. `src/ast_tools/lsp/config_watcher.py` — Hot Reload
```python
class ConfigWatcher:
    """Watches ast-tools.yaml / pyproject.toml for changes and reloads config."""
    
    def __init__(self, server: ASTToolsLanguageServer):
        self.server = server
        self._watched_files: set[Path] = set()
    
    async def start(self):
        """Begin watching config files in workspace folders."""
        pass
    
    async def on_config_change(self, path: Path):
        """Reload UnifiedConfig and reinitialize components."""
        pass
```

### 5. CLI Entry Point
Add `ast lsp` command in `cli.py`:
```python
def cmd_lsp(args: argparse.Namespace) -> int:
    """Start LSP server (stdio by default)."""
    from ast_tools.lsp.server import ASTToolsLanguageServer
    
    server = ASTToolsLanguageServer()
    server.start_io()  # stdio transport
    return 0
```

---

## Configuration Integration

The server must load `UnifiedConfig` with precedence:
1. Defaults
2. `pyproject.toml` `[tool.ast-tools]`
3. `~/.config/ast-tools/ast-tools.yaml`
4. Workspace folder `ast-tools.yaml`
5. LSP `workspace/didChangeConfiguration` (runtime override)

---

## Tests Required

| Test | Description |
|------|-------------|
| `test_lsp_initialize` | Handshake returns correct capabilities |
| `test_lsp_did_open` | Opening file triggers diagnostic publish |
| `test_lsp_did_change` | Changes debounced, diagnostics updated |
| `test_lsp_did_save` | Save triggers fix pipeline if configured |
| `test_language_router` | Extension → language → fixers mapping correct |
| `test_config_hot_reload` | Config change reloads without restart |
| `test_custom_fixer_plugin` | Plugin fixers loaded and used |

---

## Acceptance Criteria

- [ ] `ast lsp` starts and responds to `initialize`
- [ ] Opening a Python file shows Ruff diagnostics in editor
- [ ] Editing file updates diagnostics (debounced)
- [ ] Saving file runs fix pipeline (if `fix_on_save: true`)
- [ ] Config changes in `ast-tools.yaml` hot-reload
- [ ] All 255 existing tests still pass
- [ ] New LSP tests pass