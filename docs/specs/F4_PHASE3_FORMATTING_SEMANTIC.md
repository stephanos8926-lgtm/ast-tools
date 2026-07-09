# F4 LSP Server — Phase 3: Formatting & Semantic Features

**Phase:** 3 of 5
**Duration:** 2 days
**Dependencies:** Phase 1, 2 complete
**Status:** Planned

---

## Scope

Implement document formatting, range formatting, and leverage `ast-tools` semantic analysis for advanced refactoring code actions.

---

## Deliverables

### 1. `src/ast_tools/lsp/formatting.py` — Formatting Handler
```python
class FormattingHandler:
    """Handles textDocument/formatting and textDocument/rangeFormatting."""
    
    def __init__(self, server: ASTToolsLanguageServer):
        self.server = server
        self.fix_engine: FixEngine = server.fix_engine
    
    async def formatting(self, params: DocumentFormattingParams) -> list[TextEdit] | None:
        """Format entire document via fix pipeline."""
        # Run fix engine in check-only mode for the document
        # Return TextEdits for all formatting changes
        pass
    
    async def range_formatting(self, params: DocumentRangeFormattingParams) -> list[TextEdit] | None:
        """Format specific range."""
        # Similar to full formatting but constrained to range
        pass
```

### 2. `src/ast_tools/lsp/semantic_actions.py` — Semantic Refactorings
Leverage existing `ast-tools` MCP tools:
- `ast_refactor_extract_interface` → `refactor.extract.interface`
- `ast_generate_stub` → `refactor.generate.stub`
- `ast_edit` (rename, extract) → `refactor.rename`, `refactor.extract.function`
- `structural_analysis` → `refactor.inline`, `refactor.convert`

```python
class SemanticActionProvider:
    """Provides refactor code actions using ast-tools semantic analysis."""
    
    def __init__(self, server: ASTToolsLanguageServer):
        self.server = server
    
    async def get_refactor_actions(self, uri: str, range_: Range, language: str) -> list[CodeAction]:
        """Get refactor actions available at position/range."""
        actions = []
        
        # Extract function/method
        if language in ("python", "typescript", "javascript", "go", "rust"):
            actions.append(self._extract_function_action(uri, range_))
        
        # Extract variable
        actions.append(self._extract_variable_action(uri, range_))
        
        # Inline variable/function
        actions.append(self._inline_action(uri, range_))
        
        # Rename symbol
        actions.append(self._rename_action(uri, range_))
        
        # Generate stub/interface (Python)
        if language == "python":
            actions.append(self._extract_interface_action(uri, range_))
            actions.append(self._generate_stub_action(uri, range_))
        
        return actions
```

### 3. Integration with Existing MCP Tools
The LSP server should reuse the existing tool implementations:
- Call `_tool_ast_refactor_extract_interface` for interface extraction
- Call `_tool_ast_generate_stub` for stub generation
- Call `_tool_ast_edit` for rename/extract operations
- Call `_tool_structural_analysis` for callers/callees info

---

## Configuration

Uses `UnifiedConfig.lsp.formatting` and `UnifiedConfig.lsp.code_action_kind`.

---

## Tests Required

| Test | Description |
|------|-------------|
| `test_formatting_full` | Full document formatting returns correct TextEdits |
| `test_formatting_range` | Range formatting constrains to selection |
| `test_format_on_save` | Saving triggers formatting when enabled |
| `test_extract_function` | Extract function refactoring works |
| `test_extract_variable` | Extract variable refactoring works |
| `test_inline_variable` | Inline variable refactoring works |
| `test_rename_symbol` | Rename symbol works across file |
| `test_extract_interface` | Extract interface works for Python classes |
| `test_generate_stub` | Generate .pyi stub works |

---

## Acceptance Criteria

- [ ] `Shift+Alt+F` (or editor equivalent) formats document via fix pipeline
- [ ] Range formatting works on selection
- [ ] Format on save works when enabled
- [ ] Right-click → Refactor shows Extract Function/Variable/Interface
- [ ] Rename symbol (F2) works across file
- [ ] Stub generation (.pyi) available for Python
- [ ] All Phase 1-3 tests pass