# F4 LSP Server — Phase 2: Code Actions & Fix Pipeline

**Phase:** 2 of 5
**Duration:** 3 days
**Dependencies:** Phase 1 complete
**Status:** Planned

---

## Scope

Implement `textDocument/codeAction` — the core feature that exposes the unified fix pipeline to editors. This includes quick fixes, "Fix All" actions, refactorings, and LLM-assisted fixes.

---

## Deliverables

### 1. `src/ast_tools/lsp/code_actions.py` — Code Action Handler
```python
class CodeActionHandler:
    """Handles textDocument/codeAction and codeAction/resolve."""
    
    def __init__(self, server: ASTToolsLanguageServer):
        self.server = server
        self.fix_engine: FixEngine = server.fix_engine
        self.language_router: LanguageRouter = server.language_router
        self.llm_client: LLMClient = server.llm_client
    
    async def code_action(self, params: CodeActionParams) -> list[CodeAction]:
        """Main code action endpoint."""
        # 1. Get document, language, range
        # 2. Run fixers in check-only mode for the range
        # 3. Build quickfix actions from diagnostics
        # 4. Build source.fixAll action
        # 5. Build source.organizeImports action
        # 6. Build refactor actions (if semantic analysis available)
        # 7. Build LLM fix action (if enabled + available)
        pass
    
    async def code_action_resolve(self, action: CodeAction) -> CodeAction:
        """Lazy resolution for large edits (fixAll, LLM fix)."""
        # If action.data indicates lazy resolution needed:
        # 1. Compute full WorkspaceEdit
        # 2. Attach to action.edit
        # 3. Return complete action
        pass
```

### 2. Action Types & Kinds

| Kind | Title | When Available | Edit Computation |
|------|-------|----------------|------------------|
| `quickfix` | "Remove unused import" | Per diagnostic with `data.fixable=true` | Immediate (small) |
| `source.fixAll` | "ast-tools: Fix all issues (safe)" | Any file with fixable issues | Lazy (resolve) |
| `source.fixAll.unsafe` | "ast-tools: Fix all issues (incl. unsafe)" | `include_unsafe_fixall: true` | Lazy |
| `source.organizeImports` | "Organize imports" | Python/TS/Go/Rust files | Immediate |
| `refactor.extract` | "Extract function" | Selection in function body | Lazy |
| `refactor.inline` | "Inline variable" | Selection on variable | Immediate |
| `ast-tools.llmFix` | "🤖 AI: Suggest fix" | Any diagnostic, LLM enabled | Lazy |

### 3. CodeAction Data Payloads

```python
# Quickfix action
{
    "action_type": "quickfix",
    "diagnostic_code": "F401",
    "fixer": "ruff",
    "safety": "safe"
}

# FixAll action (lazy)
{
    "action_type": "fix_all",
    "safety": "safe",
    "uri": "file:///path/to/file.py",
    "languages": ["python"]
}

# LLM Fix action (lazy)
{
    "action_type": "llm_fix",
    "diagnostic_code": "E123",
    "uri": "file:///path/to/file.py",
    "language": "python"
}
```

### 4. `src/ast_tools/lsp/fix_action_builder.py` — Converts FixActions → CodeActions
```python
class FixActionBuilder:
    """Builds LSP CodeAction objects from internal FixAction objects."""
    
    @staticmethod
    def quickfix_from_fix_action(action: FixAction, diagnostic: Diagnostic) -> CodeAction:
        """Create quickfix CodeAction from FixAction."""
        return CodeAction(
            title=f"{action.tool}: {action.description}",
            kind=CodeActionKind.QuickFix,
            diagnostics=[diagnostic],
            edit=WorkspaceEdit(changes={action.file_path: [to_text_edit(action)]}),
            is_preferred=action.safety == "safe",
            data={"action_type": "quickfix", "fixer": action.tool, "safety": action.safety}
        )
    
    @staticmethod
    def fix_all_action(uri: str, languages: list[str], safety: str) -> CodeAction:
        """Create lazy fixAll action."""
        return CodeAction(
            title=f"ast-tools: Fix all issues ({safety})",
            kind=CodeActionKind.SourceFixAll,
            data={"action_type": "fix_all", "safety": safety, "uri": uri, "languages": languages}
        )
    
    @staticmethod
    def llm_fix_action(diagnostic: Diagnostic, uri: str, language: str) -> CodeAction:
        """Create LLM-assisted fix action."""
        return CodeAction(
            title="🤖 AI: Suggest fix for this issue",
            kind=CodeActionKind.Refactor,  # Custom: "ast-tools.llmFix"
            diagnostics=[diagnostic],
            data={"action_type": "llm_fix", "diagnostic_code": diagnostic.code, "uri": uri, "language": language}
        )
```

### 5. `src/ast_tools/lsp/llm_client.py` — Unified LLM Interface
```python
class LLMClient:
    """Unified interface for local + remote LLM fix suggestions."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._local_client = None
        self._remote_client = None
    
    async def is_available(self) -> bool:
        """Check if any backend is responsive."""
        pass
    
    async def suggest_fix(self, context: LLMFixContext) -> LLMFixResult:
        """
        1. Build prompt from context
        2. Try local backend first if prefer_local
        3. Fall back through remote chain
        4. Parse response as unified diff
        5. Validate diff applies cleanly
        """
        pass
    
    async def _try_local(self, prompt: str) -> LLMFixResult:
        """Try local backend (llama.cpp / ollama / vllm)."""
        pass
    
    async def _try_remote(self, prompt: str, provider: str) -> LLMFixResult:
        """Try remote provider."""
        pass
```

### 6. `src/ast_tools/lsp/diff_parser.py` — Diff Validation
```python
def parse_and_validate_diff(diff: str, original_content: str, file_path: Path) -> list[TextEdit]:
    """
    Parse unified diff, validate it applies cleanly to original_content,
    return list of LSP TextEdit objects.
    """
    pass
```

---

## Configuration Integration

Uses `UnifiedConfig.lsp.llm` and `UnifiedConfig.lsp.code_action_kind`.

---

## Tests Required

| Test | Description |
|------|-------------|
| `test_code_action_quickfix` | Single diagnostic → quickfix action with edit |
| `test_code_action_fix_all` | fixAll action returns lazy action, resolve computes edit |
| `test_code_action_organize_imports` | Organize imports action works |
| `test_code_action_llm_fix` | LLM fix action appears when enabled, resolves to diff |
| `test_code_action_safety` | Unsafe fixes only appear when configured |
| `test_diff_parser` | Various diff formats parse correctly |
| `test_llm_client_local` | Local backend tried first, falls back on failure |
| `test_llm_client_remote` | Remote chain tried in order |

---

## Acceptance Criteria

- [ ] Clicking 💡 on diagnostic shows "Quick fix" + "Fix all (safe)" + "Fix all (unsafe)" + "AI: Suggest fix"
- [ ] Quick fix applies single diagnostic fix immediately
- [ ] "Fix all" computes full WorkspaceEdit on resolve, applies all safe fixes
- [ ] "Fix all (unsafe)" includes unsafe fixes when configured
- [ ] Organize imports works for Python/TS/Go/Rust
- [ ] LLM fix action appears when LLM enabled + backend available
- [ ] LLM fix returns valid unified diff that applies cleanly
- [ ] Local LLM tried first, remote fallback works
- [ ] All Phase 1 + Phase 2 tests pass