# Phase 8: Forward Audit Assessment

## Executive Summary

**Verdict:** ✅ **FEASIBLE** — All pre-conditions met, no blocking issues identified.

---

## 1. Infrastructure Readiness

### ✅ Embeddings Layer — READY
- **Location:** `src/ast_tools/embeddings/`
- **Model:** bge-small-en-v1.5 (384 dim, CPU-only)
- **API:** `generate_embedding(text)` → `np.ndarray`
- **Batch:** `generate_batch_embeddings(texts)` → `list[np.ndarray]`
- **Status:** Fully implemented, no blockers

### ✅ sqlite-vec Integration — READY
- **Location:** `src/ast_tools/embeddings/store.py`
- **Functions:**
  - `load_vec_extension(conn)` — Load extension
  - `insert_embedding(conn, symbol_id, embedding)` — Store vector
  - `search_similar(conn, query_vector, k=10)` — KNN search
  - `get_symbols_without_embeddings(conn)` — Backfill candidates
- **Status:** Fully implemented, uses BLOB storage format

### ✅ Token Counting — READY
- **Library:** `tiktoken` (OpenAI's tokenizer)
- **Availability:** Installed in `.venv`
- **Usage:** Can estimate tokens for context budget management
- **Status:** Available for immediate use

### ✅ Database Schema — READY
- **Location:** `src/ast_tools/database/schema.py`
- **Virtual Table:** `symbols_vec` (sqlite-vec)
- **Columns:** `symbol_id TEXT PRIMARY KEY, embedding BLOB`
- **Integration:** Loads vec extension on connection (graceful degradation if not installed)

---

## 2. Architecture Validation

### ✅ No Circular Import Risk

**Proposed structure:**
```
src/ast_tools/context/
├── __init__.py          # imports: embeddings, database, formatters
├── injector.py          # imports: database.schema, embeddings.store, context.history
├── history.py           # imports: stdlib only (datetime, dataclasses)
└── formatters.py        # imports: dataclasses, markdown templating
```

**Dependency graph:**
- `context/injector.py` → `embeddings/store.py` ✓ (no reverse import)
- `context/injector.py` → `database/schema.py` ✓ (no reverse import)
- `context/formatters.py` → stdlib only ✓
- `context/history.py` → stdlib only ✓

**Tools that will import context:**
- `tools/semantic_search.py` → `context/injector.py` ✓
- `tools/ast_read.py` → `context/injector.py` ✓
- `tools/structural_analysis.py` → `context/injector.py` ✓

**No cycles detected.**

---

## 3. Hermes Hook Integration

### ⚠️ Hooks Not Currently Configured

**Current state:**
```bash
grep -A5 "pre_tool_call" ~/.hermes/config.yaml
# Returns: empty (no hooks configured)
```

**Required setup:**
1. Create hook script: `~/.hermes/scripts/context-injector-hook.sh`
2. Add to config.yaml under `hooks:` section
3. Create allowlist entry: `~/.hermes/shell-hooks-allowlist.json`
4. Hook paths MUST be absolute: `/home/sysop/.hermes/scripts/...`

**Feasibility:** ✅ Straightforward — documented pattern, no blockers

---

## 4. Performance Considerations

### Embedding Generation (CPU, 4GB RAM)
- **Model:** bge-small-en-v1.5 (~130MB)
- **Inference time:** ~50-100ms per embedding (single batch)
- **Batch (32):** ~500ms
- **Memory:** ~500MB during inference
- **Risk:** ⚠️ May pressure 4GB RAM if other processes active

**Mitigation:**
- Pre-compute embeddings in background (watcher daemon)
- Cache loaded model in module-level singleton
- Lazy load on first use

### Vector Search Performance
- **sqlite-vec:** C extension, very fast (~1ms for 1000 vectors)
- **KNN search:** O(n) but optimized in C
- **Risk:** ✅ Low

---

## 5. Configuration Requirements

### Project Config (`.ast-tools/context.yaml`)
```yaml
enabled: true
model_context_window: 32000
max_symbols: 10
diversity_limit: 3
weights:
  semantic: 0.40
  recency: 0.15
  usage: 0.15
  kind: 0.10
  proximity: 0.10
  callgraph: 0.10
```

**File creation:** Required (new file)
**Default values:** Sensible defaults exist

### Hermes Config (`~/.hermes/config.yaml`)
```yaml
hooks:
  - event: pre_tool_call
    match: "semantic_search"
    command: "/home/sysop/.hermes/scripts/context-injector-hook.sh"
```

**File modification:** Required
**Risk:** ⚠️ Manual step (can't auto-modify Hermes config per SOUL.md rules)

---

## 6. Edge Cases to Handle

### 1. No Embeddings Available
- **Scenario:** sqlite-vec not installed OR zero embeddings in DB
- **Fallback:** Skip semantic scoring, use keyword-only FTS5
- **User experience:** Degrades gracefully to "search without semantic"

### 2. Token Budget Exceeded
- **Scenario:** Context already full (>80% used)
- **Response:** Return `eviction_warnings` in result, suggest user clear context
- **Fail-safe:** Never truncate last 2 user messages

### 3. Zero Search Results
- **Scenario:** Query matches nothing
- **Response:** Return empty context with message "No relevant symbols found"
- **User experience:** Clear feedback, no confusing partial matches

### 4. Diversity Constraint Conflict
- **Scenario:** Top 10 symbols all from same file
- **Enforcement:** Hard cap at 3 symbols per file, skip remainder
- **Trade-off:** Lower relevance scores for diversity

### 5. Model With Tiny Context (2B params, 4K window)
- **Scenario:** User runs tiny local model
- **Adjustment:** Auto-detect via config, reduce to 3 symbols max
- **Graceful:** Works but limited utility

---

## 7. Required Pre-Conditions

### Must Have (blockers):
- ✅ `sqlite-vec` Python package installed
- ✅ `tiktoken` installed
- ✅ Embedding model downloaded (cached on first run)

### Must Configure (manual steps):
- ⏳ Create `.ast-tools/context.yaml` (project config)
- ⏳ Create `~/.hermes/scripts/context-injector-hook.sh` (hook script)
- ⏳ Update `~/.hermes/config.yaml` with hook entry
- ⏳ Create `~/.hermes/shell-hooks-allowlist.json` entry

### Nice to Have (not blockers):
- ⏳ Hermes hook testing (verify pre_tool_call fires)
- ⏳ Token counting accuracy validation
- ⏳ Performance benchmarks on 4GB RAM system

---

## 8. Implementation Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| RAM pressure during embedding gen | Medium | Medium | Background jobs, model caching |
| Hermes hook integration fails | Low | High | Test hooks inline, provide non-hook fallback |
| Token counting inaccurate | Medium | Low | Over-estimate to be safe, add buffer |
| Vector search slow on large indices | Low | Medium | Add index on embedding column, limit K |
| User config mistakes | Medium | Low | Provide sensible defaults, validate config |

**Overall Risk:** 🟡 **LOW-MEDIUM** — Manageable with testing

---

## 9. Test Strategy

### Unit Tests (pytest)
- `test_context_injector.py` — Relevance scoring calculations
- `test_history_tracking.py` — Injection history, staleness
- `test_formatters.py` — Markdown output, token counting
- `test_budget_management.py` — Edge cases (full context, tiny models)

### Integration Tests
- `test_semantic_search_with_context.py` — End-to-end search flow
- `test_hermes_hook_integration.py` — Hook fires, context injected
- `test_diversity_enforcement.py` — 3 symbols/file limit

### Manual Tests (user)
- TUI interaction with context injection
- Hermes CLI with hook enabled
- Token budget validation on various models

---

## Conclusion

**Phase 8 is READY for implementation.**

All infrastructure exists (embeddings, sqlite-vec, tiktoken). Architecture has no circular import risk. Configuration is straightforward. Edge cases are identified and manageable.

**Next step:** Reverse Audit (identify gaps, security concerns, performance optimizations)

**Estimated implementation time:** 3-4 hours inline, or 2h with parallel subagent dispatch

---

## Appendix: File Locations

**To Create:**
- `src/ast_tools/context/__init__.py`
- `src/ast_tools/context/injector.py` (~400 lines)
- `src/ast_tools/context/history.py` (~150 lines)
- `src/ast_tools/context/formatters.py` (~100 lines)
- `.ast-tools/context.yaml`
- `~/.hermes/scripts/context-injector-hook.sh`
- `~/.hermes/shell-hooks-allowlist.json` (update existing)

**To Modify:**
- `src/ast_tools/tools/semantic_search.py`
- `src/ast_tools/tools/ast_read.py`
- `src/ast_tools/tools/structural_analysis.py`
- `src/ast_tools/tools/__init__.py`
- `~/.hermes/config.yaml`

**No files to delete or break.**