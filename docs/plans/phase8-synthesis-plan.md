# Phase 8: Context Injection — Implementation Plan

## Synthesis of Forward + Reverse Audits

**Date:** 2026-07-24
**Mode:** HIGH (security-critical, affects all agent interactions)
**Status:** Ready for sign-off ✅

---

## Architecture Decision Summary

### Core Components

| Component | Location | Lines | Dependencies |
|-----------|----------|-------|--------------|
| `ContextInjector` | `src/ast_tools/context/injector.py` | ~400 | embeddings, database, tiktoken |
| `InjectionHistory` | `src/ast_tools/context/history.py` | ~150 | stdlib only |
| `MarkdownFormatter` | `src/ast_tools/context/formatters.py` | ~100 | tiktoken |
| Context tools | `src/ast_tools/tools/context_tools.py` | ~100 | context.injector |

**Total new code:** ~750 lines
**Tests:** ~400 lines (4 test files)

---

## Implementation Phases

### Phase 8A: Core Infrastructure (2-3 hours)

**Step 1:** Create package structure
```bash
mkdir -p src/ast_tools/context
touch src/ast_tools/context/__init__.py
```

**Step 2:** Implement `injection_history.py` (easiest, no deps)
- Session-based tracking
- Injection counts, timestamps
- Diversity enforcement

**Step 3:** Implement `formatters.py`
- Markdown templating
- Token counting with tiktoken
- Output formatting

**Step 4:** Implement `injector.py` (core logic)
- Relevance scoring (6 factors)
- Budget management
- sqlite-vec integration
- Fallback behavior

**Step 5:** Implement `context_tools.py`
- MCP tool wrappers
- Manual override tools

---

### Phase 8B: Integration (1 hour)

**Step 6:** Modify existing tools
- `semantic_search.py` → inject context after search
- `ast_read.py` → inject related symbols
- `structural_analysis.py` → inject dependency chain

**Step 7:** Register tools
- Update `tools/__init__.py`
- Add to TOOL_REGISTRY

**Step 8:** Create config
- `.ast-tools/context.yaml` (project)
- `~/.hermes/config.yaml` (hooks)
- `~/.hermes/scripts/context-injector-hook.sh`
- `~/.hermes/shell-hooks-allowlist.json`

---

### Phase 8C: Testing & Validation (1-2 hours)

**Unit tests:**
- `test_injector.py` — scoring, budget, diversity
- `test_history.py` — tracking, staleness
- `test_formatters.py` — markdown, tokens
- `test_fallback.py` — no sqlite-vec, no embeddings

**Integration tests:**
- `test_semantic_search_context.py` — end-to-end
- `test_hook_integration.py` — manual script

**Manual validation:**
- TUI testing
- Token budget verification
- Performance on 4GB RAM

---

## Security Checklist (HIGH mode requirement)

- [ ] Hook script uses `set -euo pipefail`
- [ ] Hook script logs to stderr only
- [ ] Hook script NEVER writes temp files
- [ ] Hook script permissions: `chmod 700`
- [ ] Config validation rejects invalid weights
- [ ] Graceful degradation if sqlite-vec fails
- [ ] No API keys/secrets in injected context
- [ ] No user input executed without sanitization

---

## Performance Safeguards

1. **Model caching:** Singleton pattern for bge-small model
2. **Token caching:** Cache tiktoken counts per symbol
3. **Pre-filter vector search:** FTS5 first, then KNN on candidates
4. **Limit injections:** Max 10 symbols, 3 per file
5. **Background embedding:** Watcher daemon handles bulk generation

---

## Rollback Plan

If Phase 8 breaks anything:

**Immediate rollback:**
```bash
# Disable hooks in Hermes config
# Comment out hook entry in ~/.hermes/config.yaml

# Or disable in project config
echo "enabled: false" > .ast-tools/context.yaml
```

**Code rollback:**
```bash
cd ~/Workspaces/ast-tools
git revert <phase8-commits>
```

**No breaking changes:** Context injection is additive, no existing behavior modified.

---

## Definition of Done (HIGH mode)

- [x] Spec written (`docs/phase8-context-injection-spec.md`)
- [x] Forward audit complete (`docs/phase8-forward-audit.md`)
- [x] Reverse audit complete (`docs/phase8-reverse-audit-1.md`, `...-2.md`)
- [x] Synthesis + plan written (this document)
- [ ] User sign-off (Steven approves)
- [ ] TDD: Tests written FIRST, then implementation
- [ ] All tests passing + integration tests
- [ ] Adversarial audit complete (security + edge cases)
- [ ] Lint + dead code check complete
- [ ] Documentation updated (README.md, CONTEXT.md)
- [ ] Hook tested manually on workstation
- [ ] Performance validated on 4GB RAM system

---

## Token Budget (for this implementation)

**Estimated:**
- Planning/audits: ~8K tokens (done)
- Implementation: ~15K tokens (750 lines code + 400 lines tests)
- Testing: ~5K tokens
- Documentation: ~3K tokens
- **Total:** ~31K tokens

**Within limits:** ✅ Yes (32K context window typical)

---

## Next Step: User Sign-off

**Steven,** please confirm:

1. Architecture looks correct?
2. Relevance scoring weights reasonable? (semantic 40%, etc.)
3. Token budget conservative enough?
4. Security mitigations adequate?
5. **Proceed with TDD implementation?**

Reply "GO" to proceed, or flag concerns.