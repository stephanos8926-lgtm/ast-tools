# Implementation Plans History

This document contains all historical implementation plans consolidated.

---

## EASY_WINS_PLAN_v1

# Easy Wins Implementation Plan — CLI Tool + Dead Code Detection

**Date:** 2026-06-28  
**Mode:** MEDIUM (TDD mandatory, audits required)  
**Version:** 1.0  
**Status:** DRAFT — Pending Audits

---

## File Manifest

### New Files (CLI Tool)

| File | Lines (est) | Purpose | Dependencies |
|------|-------------|---------|--------------|
| `src/ast_tools/cli.py` | 200 | Main CLI entry point (argparse, command routing) | argparse, rich |
| `src/ast_tools/cli/formatters.py` | 120 | Output formatters (markdown, JSON, tree, compact) | rich, json |
| `src/ast_tools/cli/commands/search.py` | 80 | `ast-tools search` command | formatters, semantic_search |
| `src/ast_tools/cli/commands/nav.py` | 50 | `ast-tools nav` command | formatters, find_symbol_definition |
| `src/ast_tools/cli/commands/blast_radius.py` | 70 | `ast-tools blast-radius` command | formatters, impact_analysis |
| `src/ast_tools/cli/commands/index_status.py` | 40 | `ast-tools index-status` command | formatters, database |
| `src/ast_tools/cli/__init__.py` | 20 | CLI package init | — |
| `src/ast_tools/cli/commands/__init__.py` | 10 | Commands package init | — |
| `tests/test_cli.py` | 150 | CLI unit + integration tests | pytest, click.testing |

### New Files (Dead Code Detection)

| File | Lines (est) | Purpose | Dependencies |
|------|-------------|---------|--------------|
| `src/ast_tools/tools/dead_code.py` | 180 | Dead code detection tool | database, queries |
| `src/ast_tools/decorator_detector.py` | 100 | Framework decorator detection (Flask, FastAPI, Django) | ast, tree-sitter |
| `tests/test_dead_code.py` | 200 | Dead code detection tests | pytest, tempfile |
| `tests/test_decorator_detector.py` | 120 | Decorator detection tests | pytest |

### Modified Files

| File | Changes | Purpose |
|------|---------|---------|
| `pyproject.toml` | Add `[project.scripts]` entry point | Register `ast-tools` CLI command |
| `src/ast_tools/tools/__init__.py` | Register `_tool_find_dead_code()` | MCP tool registration |
| `README.md` | Add CLI usage examples | Documentation |
| `docs/CLI_USAGE.md` | New file | CLI user guide |

**Total:** 12 new files, 4 modified files  
**Estimated effort:** 1,340 lines of new code

---

## Implementation Phases (Ordered)

### Phase 1: CLI Skeleton (Day 1, 3h)

**Goal:** Minimal CLI that runs and shows help

**Tasks:**
1. Create `src/ast_tools/cli/` package structure
2. Implement `src/ast_tools/cli/__init__.py` (empty)
3. Implement `src/ast_tools/cli/commands/__init__.py` (empty)
4. Implement `src/ast_tools/cli.py` with argparse skeleton
5. Add `--help` support for all 6 commands (no implementation yet)
6. Update `pyproject.toml` with entry point
7. Test: `ast-tools --help` works
8. Test: `ast-tools search --help` shows args

**Acceptance criteria:**
- [ ] `ast-tools --help` shows 6 commands
- [ ] `ast-tools search --help` shows args
- [ ] Entry point registered in pyproject.toml
- [ ] No circular imports

**Commit:** `feat(cli): add CLI skeleton with argparse structure`

---

### Phase 2: Index Status Command (Day 1, 2h)

**Goal:** First working command (easiest, read-only)

**Tasks:**
1. Implement `src/ast_tools/cli/commands/index_status.py`
2. Wire to `cli.py` command router
3. Implement `format_as_markdown()` for index stats
4. Test: `ast-tools index-status` returns stats
5. Test: `ast-tools index-status --format=json` returns valid JSON

**Acceptance criteria:**
- [ ] Shows files indexed, symbols, embeddings count
- [ ] Markdown format works
- [ ] JSON format works
- [ ] Handles empty index gracefully

**Commit:** `feat(cli): implement index-status command`

---

### Phase 3: Search Command (Day 2, 4h)

**Goal:** Core search functionality

**Tasks:**
1. Implement `src/ast_tools/cli/formatters.py` (all 4 formats)
2. Implement `src/ast_tools/cli/commands/search.py`
3. Wire to `hybrid_search_with_context()` from semantic_search module
4. Implement markdown formatter (rich markdown)
5. Implement JSON formatter
6. Implement tree formatter (hierarchical)
7. Implement compact formatter (file:line only)
8. Test all 4 output formats
9. Test with various queries

**Acceptance criteria:**
- [ ] Search returns results in all 4 formats
- [ ] Respects `--limit`, `--lang`, `--kind` filters
- [ ] Markdown output is readable
- [ ] JSON output is valid and parseable
- [ ] Compact output is script-friendly

**Commit:** `feat(cli): implement search command with 4 output formats`

---

### Phase 4: Navigation Commands (Day 2, 3h)

**Goal:** nav, callers, callees commands

**Tasks:**
1. Implement `src/ast_tools/cli/commands/nav.py` (symbol definition lookup)
2. Implement `src/ast_tools/cli/commands/blast_radius.py` (callers + callees)
3. Wire `callers` and `callees` as aliases to `blast-radius --direction=X`
4. Test all navigation commands

**Acceptance criteria:**
- [ ] `ast-tools nav SessionManager` finds definition
- [ ] `ast-tools callers foo` lists callers
- [ ] `ast-tools blast-radius foo` shows impact
- [ ] Handles symbol not found gracefully

**Commit:** `feat(cli): implement nav, callers, blast-radius commands`

---

### Phase 5: Dead Code Detection Core (Day 3, 4h)

**Goal:** Core algorithm (find unreferenced symbols)

**Tasks:**
1. Implement `src/ast_tools/tools/dead_code.py` (core algorithm)
2. Implement `find_unreferenced_symbols()` SQL query
3. Implement `filter_false_positives()` with 5 exclusion categories:
   - Magic methods (`__init__`, `__str__`, etc.)
   - Entry points (`main`, `if __name__ == '__main__'`)
   - Framework decorators (Flask route, FastAPI endpoint)
   - Override methods
   - `__all__` exports
4. Implement `has_decorator()` helper
5. Implement `is_override()` helper
6. Test core detection logic
7. Test false positive filtering

**Acceptance criteria:**
- [ ] Finds unreferenced functions in test project
- [ ] Excludes magic methods
- [ ] Excludes entry points
- [ ] Returns confidence scores
- [ ] Summary stats are accurate

**Commit:** `feat(dead-code): implement core detection algorithm`

---

### Phase 6: Decorator Detector (Day 4, 3h)

**Goal:** Framework-aware detection

**Tasks:**
1. Implement `src/ast_tools/decorator_detector.py`
2. Support Flask (`@app.route`, `@blueprint.route`)
3. Support FastAPI (`@app.get`, `@app.post`, `@router.get`)
4. Support Django (`@login_required`, `@api_view`)
5. Test decorator detection

**Acceptance criteria:**
- [ ] Detects Flask routes
- [ ] Detects FastAPI endpoints
- [ ] Detects Django views
- [ ] Handles nested decorators
- [ ] >90% accuracy on test fixtures

**Commit:** `feat(decorator-detector): support Flask, FastAPI, Django`

---

### Phase 7: MCP Tool Registration (Day 4, 2h)

**Goal:** Expose dead code as MCP tool

**Tasks:**
1. Register `_tool_find_dead_code()` in `src/ast_tools/tools/__init__.py`
2. Add to MCP server tool list
3. Test via MCP: `find_dead_code(project_path)`
4. Document tool usage in README

**Acceptance criteria:**
- [ ] MCP tool callable via Hermes
- [ ] Returns expected JSON structure
- [ ] Works with project_path parameter
- [ ] Listed in MCP tool discovery

**Commit:** `feat(mcp): register find_dead_code tool`

---

### Phase 8: CLI Integration for Dead Code (Day 5, 2h)

**Goal:** CLI command: `ast-tools find-dead`

**Tasks:**
1. Implement `src/ast_tools/cli/commands/find_dead.py`
2. Wire to CLI command router
3. Implement markdown report format
4. Test CLI command
5. Test all output formats

**Acceptance criteria:**
- [ ] `ast-tools find-dead` returns report
- [ ] Markdown format shows code snippets
- [ ] JSON format is machine-readable
- [ ] Summary stats are accurate

**Commit:** `feat(cli): implement find-dead command`

---

### Phase 9: TDD — CLI Tests (Day 5, 3h)

**Goal:** Full test coverage for CLI

**Tasks:**
1. Implement `tests/test_cli.py` with tests for:
   - `test_cli_index_status_markdown()`
   - `test_cli_index_status_json()`
   - `test_cli_search_markdown()`
   - `test_cli_search_json()`
   - `test_cli_search_compact()`
   - `test_cli_nav()`
   - `test_cli_blast_radius()`
   - `test_cli_find_dead()`
   - `test_cli_error_handling()`  (invalid args, missing index)
2. Run all tests (RED first, then GREEN)
3. Ensure >90% coverage

**Acceptance criteria:**
- [ ] All tests pass
- [ ] Coverage >90%
- [ ] Error cases covered
- [ ] No flaky tests

**Commit:** `test(cli): add comprehensive CLI test suite`

---

### Phase 10: TDD — Dead Code Tests (Day 6, 3h)

**Goal:** Full test coverage for dead code detection

**Tasks:**
1. Implement `tests/test_dead_code.py`:
   - `test_find_dead_code_basic()`
   - `test_skip_magic_methods()`
   - `test_skip_entry_points()`
   - `test_skip_flask_routes()`
   - `test_skip_fastapi_endpoints()`
   - `test_skip_overrides()`
   - `test_skip_all_exports()`
   - `test_confidence_scoring()`
2. Implement `tests/test_decorator_detector.py`:
   - `test_detect_flask_decorators()`
   - `test_detect_fastapi_decorators()`
   - `test_detect_django_decorators()`
   - `test_nested_decorators()`
3. Run tests (RED first, then GREEN)

**Acceptance criteria:**
- [ ] All tests pass
- [ ] Coverage >90%
- [ ] Edge cases covered
- [ ] False positive rate <20%

**Commit:** `test(dead-code): add comprehensive test suite`

---

### Phase 11: Documentation (Day 6, 2h)

**Goal:** User-facing documentation

**Tasks:**
1. Create `docs/CLI_USAGE.md` (user guide)
2. Update `README.md` with CLI examples
3. Add CLI section to `docs/USAGE.md`
4. Document `find_dead_code()` MCP tool

**Acceptance criteria:**
- [ ] CLI_USAGE.md covers all commands
- [ ] README shows basic CLI usage
- [ ] Examples are copy-paste runnable
- [ ] All options documented

**Commit:** `docs: add CLI usage guide`

---

## Rollback Plan

**Per-phase commits** allow safe rollback:

| Phase | Rollback Command | Risk |
|-------|------------------|------|
| 1 (Skeleton) | `git reset --hard HEAD~1` | None (skeleton only) |
| 2 (Index status) | `git reset --hard HEAD~1` | None |
| 3 (Search) | `git reset --hard HEAD~1` | Low |
| 4 (Nav) | `git reset --hard HEAD~2` | Low |
| 5 (Dead code core) | `git reset --hard HEAD~5` | None (not exposed yet) |
| 6 (Decorator detector) | `git reset --hard HEAD~1` | None |
| 7 (MCP registration) | `git reset --hard HEAD~1` | Low (MCP tool only) |
| 8 (CLI find-dead) | `git reset --hard HEAD~1` | Low |
| 9-10 (Tests) | `git reset --hard HEAD~2` | None |
| 11 (Docs) | `git reset --hard HEAD~1` | None |

**Emergency rollback (all phases):**
```bash
git checkout master  # Return to pre-feature state
```

---

## Test Strategy (TDD Mandatory for MEDIUM Mode)

### Unit Tests

- CLI arg parsing (all commands, all options)
- Formatters (markdown, JSON, tree, compact)
- Dead code detection algorithm
- Decorator detection

### Integration Tests

- CLI → database connection
- CLI → MCP tool calls
- Dead code → real codebase (ast-tools repo as test case)

### Test Commands

```bash
# Run CLI tests
PYTHONPATH=src pytest tests/test_cli.py -v

# Run dead code tests
PYTHONPATH=src pytest tests/test_dead_code.py -v

# Full suite
PYTHONPATH=src pytest tests/ -q --tb=short
```

---

## Dependencies & Prerequisites

### Python Packages (Already Installed)
- ✅ `argparse` (stdlib)
- ✅ `json` (stdlib)
- ✅ `rich` (for markdown formatting, already in venv)

### Database Schema (Already Exists)
- ✅ `symbols` table (functions, classes, methods)
- ✅ `edges` table (calls, imports)
- ✅ All queries needed are implemented

### No Major Prerequisites
- CLI tool uses existing MCP tools
- Dead code detection uses existing index
- No external API keys needed
- No breaking changes to existing code

---

## Success Metrics (Per Spec)

| Metric | Target |
|--------|--------|
| CLI commands | 6 implemented |
| Output formats | 4 (markdown, JSON, tree, compact) |
| Dead code accuracy | >80% (false positive rate <20%) |
| False positive exclusions | 5+ categories |
| Test coverage | >90% |
| Lint violations | 0 (ruff clean) |

---

## Next Steps (Per plan-and-audit MEDIUM Mode)

1. ✅ **Spec complete** (EASY_WINS_SPEC_20260628.md)
2. ✅ **Plan complete** (this document)
3. ⏳ **Forward Audit** — Dispatched (validating feasibility)
4. ⏳ **Reverse Audit** — Dispatched (finding gaps)
5. ⏳ **Adversarial Audit** — To be dispatched (security focus) — **WAITING for audit results**
6. ⏳ **Bug Review** — To be dispatched (code quality) — **WAITING for audit results**
7. ⏳ **Lint Audit** — To be run on existing code (baseline)
8. ⏳ **Synthesis** — Combine audits, fix plan
9. ⏳ **Sign-off** — User approval
10. ⏳ **TDD Implementation** — Tests first, then code

---

**Status:** READY FOR AUDITS (Forward, Reverse, Adversarial, Bug Review, Lint)

*Forward and reverse audits dispatched in parallel. Waiting for results before adversarial + bug review.*
---

## phase8-synthesis-plan

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
---

## phase9-implementation-plan

# Phase 9 Schema Enrichments: Implementation Plan

**Version:** 1.0  
**Date:** 2026-07-24  
**Mode:** HIGH (20+ files, public API, schema migration, performance-critical)  
**Status:** Ready for Implementation

---

## 1. Specification Summary

From `docs/phase9-spec.md` (601 lines):

### 9.1 New Capabilities

| Feature | Description | Impact |
|---------|-------------|--------|
| **Callgraph Edges** | 4 types: `calls`, `imports`, `inherits`, `implements` | Core architecture understanding |
| **Dependency Tracking** | Fan-in/fan-out metrics, circular detection via DFS | Impact analysis, SPOF detection |
| **Embedding Similarity** | Precomputed cosine matrix, KNN graph (k=10) | "Find similar code" queries |
| **Schema Extensions** | New tables: `callgraph_edges`, `dependency_metrics`, `embedding_similarity` | Database migration required |
| **API Endpoints** | 6 new tools: `/callgraph`, `/dependencies`, `/similar`, `/cycles`, `/embeddings/compute`, `/embeddings/batch` | Enhanced MCP tool surface |
| **Performance Targets** | Index <60min (1M files), Query p50 <50ms, p95 <200ms, p99 <500ms | Infrastructure requirements |

### 9.2 Database Migration (Migration 009)

**New Tables:**
```sql
CREATE TABLE callgraph_edges (
    id INTEGER PRIMARY KEY,
    source_symbol_id INTEGER NOT NULL,
    target_symbol_id INTEGER NOT NULL,
    edge_type TEXT NOT NULL CHECK (edge_type IN ('calls', 'imports', 'inherits', 'implements')),
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_symbol_id) REFERENCES symbols(id),
    FOREIGN KEY (target_symbol_id) REFERENCES symbols(id),
    UNIQUE(source_symbol_id, target_symbol_id, edge_type)
);

CREATE TABLE dependency_metrics (
    symbol_id INTEGER PRIMARY KEY,
    fan_in INTEGER DEFAULT 0,
    fan_out INTEGER DEFAULT 0,
    sPOF_score REAL DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id)
);

CREATE TABLE embedding_similarity (
    symbol_id_1 INTEGER NOT NULL,
    symbol_id_2 INTEGER NOT NULL,
    cosine_similarity REAL NOT NULL,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol_id_1, symbol_id_2),
    FOREIGN KEY (symbol_id_1) REFERENCES symbols(id),
    FOREIGN KEY (symbol_id_2) REFERENCES symbols(id)
);

CREATE INDEX idx_embedding_sim ON embedding_similarity(symbol_id_1, cosine_similarity DESC);
```

### 9.3 New API Endpoints

```python
# New MCP tools in src/ast_tools/tools/
callgraph.py          # /callgraph, /callgraph/callees, /callgraph/callers
dependencies.py       # /dependencies, /cycles
similarity.py         # /similar, /embeddings/compute, /embeddings/batch
```

---

## 2. Implementation Roadmap

### Wave 1: Schema + Migrations (Files: 4)
**Duration:** 1-2 hours  
**Dependencies:** None

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/db/migrations/009_schema_enrichments.py` | CREATE | ~200 |
| `src/ast_tools/db/schema.py` | PATCH (add new tables) | +50 |
| `tests/db/test_migration_009.py` | CREATE | ~100 |
| `tests/db/test_schema_enrichments.py` | CREATE | ~150 |

**Success Criteria:**
- [ ] Migration 009 applied successfully
- [ ] New tables exist with correct schema
- [ ] Indexes created (idx_embedding_sim, idx_callgraph_edge_type)
- [ ] Foreign key constraints enforced
- [ ] Rollback tested

### Wave 2: Callgraph Edges (Files: 6)
**Duration:** 2-3 hours  
**Dependencies:** Wave 1 complete

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/tools/callgraph.py` | CREATE | ~300 |
| `src/ast_tools/analysis/callgraph_builder.py` | CREATE | ~250 |
| `tests/tools/test_callgraph.py` | CREATE | ~200 |
| `tests/analysis/test_callgraph_builder.py` | CREATE | ~150 |
| `docs/callgraph-edges.md` | CREATE | ~100 |
| `src/ast_tools/tools/__init__.py` | PATCH (register new tools) | +20 |

**Tools:**
1. `ast_grep_callgraph` — Build callgraph for project
2. `ast_callgraph_callees` — What does X call?
3. `ast_callgraph_callers` — Who calls X?

**Success Criteria:**
- [ ] Callgraph edges extracted via AST traversal
- [ ] 3 tools functional with correct output
- [ ] Tests pass (90%+ coverage)
- [ ] Performance: <10sec for 10K file project

### Wave 3: Dependency Tracking (Files: 5)
**Duration:** 2 hours  
**Dependencies:** Wave 2 (shares callgraph infrastructure)

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/tools/dependencies.py` | CREATE | ~250 |
| `src/ast_tools/analysis/dependency_tracker.py` | CREATE | ~200 |
| `tests/tools/test_dependencies.py` | CREATE | ~150 |
| `docs/dependency-tracking.md` | CREATE | ~80 |
| `src/ast_tools/tools/__init__.py` | PATCH | +10 |

**Tools:**
1. `ast_dependencies` — Get fan-in/fan-out for symbol
2. `ast_detect_cycles` — Find circular dependencies
3. `ast_spof_analysis` — Identify single points of failure

**Success Criteria:**
- [ ] Fan-in/fan-out computed correctly
- [ ] Cycle detection via DFS (Tarjan's or similar)
- [ ] SPOF score calculated (high fan-in + low fan-out = SPOF)
- [ ] Tests pass

### Wave 4: Embedding Similarity (Files: 6)
**Duration:** 3-4 hours  
**Dependencies:** Wave 1 (schema), Wave 3 (optional)

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/tools/similarity.py` | CREATE | ~300 |
| `src/ast_tools/embeddings/similarity_engine.py` | CREATE | ~350 |
| `src/ast_tools/embeddings/batch_computer.py` | CREATE | ~200 |
| `tests/tools/test_similarity.py` | CREATE | ~200 |
| `tests/embeddings/test_similarity_engine.py` | CREATE | ~150 |
| `docs/similarity-search.md` | CREATE | ~100 |

**Tools:**
1. `ast_similar` — Find similar code (by semantic similarity)
2. `ast_embeddings_compute` — Compute embeddings for symbols
3. `ast_embeddings_batch` — Batch compute embeddings

**Implementation Notes:**
- Use local transformer: `BAAI/bge-small-en-v1.5` (384 dim, CPU-only)
- Embeddings cached in `symbols.embeddings` (existing column)
- Similarity precomputed and cached in `embedding_similarity` table
- KNN graph: k=10 nearest neighbors per symbol

**Success Criteria:**
- [ ] Embeddings generated correctly (384-dim vectors)
- [ ] Cosine similarity computed accurately
- [ ] KNN graph built for entire codebase
- [ ] Query: <50ms p50 latency
- [ ] Batch compute: <60min for 1M symbols

### Wave 5: Performance Optimization (Files: 3)
**Duration:** 2 hours  
**Dependencies:** Waves 1-4

| File | Action | Lines |
|------|--------|-------|
| `src/ast_tools/optimization/index_tuner.py` | CREATE | ~150 |
| `src/ast_tools/optimization/query_optimizer.py` | CREATE | ~200 |
| `tests/optimization/test_performance.py` | CREATE | ~100 |

**Optimizations:**
1. **Batch inserts** — Use `executemany` for migrations
2. **Index strategies** — Partial indexes, covering indexes
3. **Query optimization** — Use CTEs, avoid N+1 queries
4. **sqlite-vec integration** — Ensure F32_BLOB storage, not TEXT

**Success Criteria:**
- [ ] Index build time: <60min for 1M symbols
- [ ] Query p50: <50ms, p95: <200ms, p99: <500ms
- [ ] Memory: <500MB peak during indexing

### Wave 6: Documentation + Integration (Files: 4)
**Duration:** 1-2 hours  
**Dependencies:** Waves 1-5

| File | Action | Lines |
|------|--------|-------|
| `docs/phase9-implementation-guide.md` | CREATE | ~300 |
| `docs/api-reference/enrichments.md` | CREATE | ~200 |
| `QUICKSTART_PHASE9.md` | CREATE | ~100 |
| `src/ast_tools/README.md` | PATCH (add new tools reference) | +50 |

---

## 3. Test Strategy

### Unit Tests
- Migration 009: Schema validation, FK constraints
- Callgraph builder: Edge extraction accuracy
- Dependency tracker: Fan-in/out, cycle detection
- Similarity engine: Cosine similarity, KNN graph

### Integration Tests
- End-to-end tool calls (MCP endpoints)
- Performance benchmarks
- Memory profiling

### Acceptance Criteria
- [ ] 90%+ code coverage
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Performance targets met
- [ ] No memory leaks (>500MB peak)

---

## 4. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration 009 breaks existing DB | Low | High | Rollback script, backup before migration |
| Performance targets not met | Medium | Medium | Profile early, optimize hot paths |
| sqlite-vec integration issues | Medium | High | Fallback to pure SQLite + FTS5 |
| Circular dependency detection slow | Low | Low | DFS with memoization, early exit |
| Embedding batch compute OOM | Medium | Medium | Chunked processing (10K symbols/batch) |

**Rollback Plan:**
```bash
# If Migration 009 fails:
cp ~/.ast-tools/ast-tools.db ~/.ast-tools/ast-tools.db.bak
# Restore from backup if needed:
cp ~/.ast-tools/ast-tools.db.bak ~/.ast-tools/ast-tools.db
```

---

## 5. Verification Checklist

Before claiming Phase 9 complete:

- [ ] All 6 new tools functional (`ast_callgraph_*`, `ast_dependencies`, `ast_detect_cycles`, `ast_similar`, `ast_embeddings_*`)
- [ ] Migration 009 applied successfully
- [ ] Indexes created and verified
- [ ] Performance benchmarks meet targets
- [ ] 90%+ test coverage
- [ ] Documentation complete
- [ ] Backward compatibility verified (old queries still work)
- [ ] Rollback tested on staging data

---

## 6. Implementation Order

**Recommended sequence:**

1. **Wave 1** (Schema + Migrations) — Foundation
2. **Wave 2** (Callgraph) — Core capability
3. **Wave 3** (Dependencies) — Builds on callgraph
4. **Wave 4** (Similarity) — Independent, but needs schema
5. **Wave 5** (Optimization) — After features work
6. **Wave 6** (Docs) — Final polish

**Parallel execution:** Waves 2 + 4 could run in parallel (independent), but Wave 3 depends on Wave 2.

---

## 7. Git Strategy

**Branch:** `feature/phase9-schema-enrichments`

**Commits:**
- `feat: Phase 9 — Migration 009 (schema enrichments)` — Wave 1
- `feat: Add callgraph edge extraction + tools` — Wave 2
- `feat: Add dependency tracking + cycle detection` — Wave 3
- `feat: Add embedding similarity + KNN graph` — Wave 4
- `perf: Optimize indexing + query performance` — Wave 5
- `docs: Add Phase 9 implementation guide + API reference` — Wave 6

**PR:** Single PR with 6 commits (or 6 smaller PRs if preferred)

---

## 8. Sign-off Required

**Before implementation begins:**

- [ ] Spec reviewed and understood
- [ ] Forward audit completed
- [ ] Reverse audit completed (if dispatched)
- [ ] Synthesis plan approved
- [ ] Mode: HIGH confirmed
- [ ] TDD approach understood (tests FIRST)

**User sign-off:** `Confirmed, proceed with HIGH mode — Steven`

---

## 9. Implementation Notes

**TDD Enforcement (HIGH mode):**
- Write failing test FIRST
- Implement minimum to pass test
- Refactor (if needed)
- Repeat for each feature

**Inline vs. Subagent:**
- **Inline:** Waves 1, 2, 3 (complex, core infrastructure)
- **Subagent:** Waves 4, 5, 6 (can be parallelized, less critical)

**Estimated Total Duration:** 10-14 hours
- Wave 1: 1-2h
- Wave 2: 2-3h
- Wave 3: 2h
- Wave 4: 3-4h
- Wave 5: 2h
- Wave 6: 1-2h

**Critical Path:** Waves 1 → 2 → 3 → 4 → 5 → 6

---

**Ready for implementation.**
---

## refactor-modular-plan-v1

# AST-Tools Modular Refactoring — Implementation Plan

> **For Hermes:** Use `subagent-driven-development` skill to implement this plan task-by-task.

**Goal:** Refactor monolithic `ast_tools_server.py` (1914 lines) into modular package structure.

**Architecture:** Professional Python package with src layout, one tool per module, shared utilities.

**Tech Stack:** Python 3.13+, libcst, pytest, ruff, MCP SDK.

**Corrections from Forward Audit:**
- ✅ src/ directory already exists (no need to create)
- ⚠️ ast-grep CLI must be installed before Phase 3
- ⚠️ Import paths need `PYTHONPATH=src` or package restructuring
- 🔍 15+ helper functions identified for extraction (not just annotations)

---

## Phase 0: Prerequisites

### Task 0.1: Install ast-grep CLI

**Objective:** Install ast-grep CLI required for the ast_grep tool (Phase 3).

**Step 1: Install via cargo (recommended)**
```bash
cargo install ast-grep-cli
# OR via pip if available
pip install ast-grep
```

**Step 2: Verify installation**
```bash
which ast-grep
ast-grep --version
```

**Step 3: Commit**
```bash
git add -A && git commit -m "chore: install ast-grep CLI dependency"
```

---

## Phase 1: Package Structure + Extract Utils

**Objective:** Create the new package structure and extract shared utilities.

### Task 1.1: Create Package Directories

**Files:**
- Create: `src/ast_tools/__init__.py`
- Create: `src/ast_tools/server.py`
- Create: `src/ast_tools/tools/__init__.py`
- Create: `src/ast_tools/utils/__init__.py`

**Step 1: Create directories**
```bash
cd ~/Workspaces/ast-tools
mkdir -p src/ast_tools/tools src/ast_tools/utils
```

**Step 2: Create `src/ast_tools/__init__.py`**
```python
"""AST-Tools MCP Server — structural code analysis and editing."""

from .server import create_server, list_tools, call_tool

__all__ = ["create_server", "list_tools", "call_tool"]
```

**Step 3: Create `src/ast_tools/server.py`** (skeleton — tools imported later)
```python
"""MCP server setup and tool registration."""

from mcp.server import Server

def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("ast-tools")
    
    @server.list_tools()
    async def list_tools():
        from .tools import get_all_tools
        return await get_all_tools()
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        from .tools import get_tool_handler
        handler = get_tool_handler(name)
        return await handler(name, arguments)
    
    return server
```

**Step 4: Create `src/ast_tools/tools/__init__.py`** (skeleton — tools added in Phase 2+)
```python
"""AST-Tools: Individual tool implementations."""

from typing import Any

TOOL_REGISTRY: dict[str, callable] = {}

def register_tool(name: str, handler: callable):
    """Register a tool handler."""
    TOOL_REGISTRY[name] = handler

async def get_all_tools():
    """Return list of all registered tools."""
    from mcp.types import Tool
    # Tools will be populated as modules are imported
    return []

def get_tool_handler(name: str) -> callable:
    """Get handler for a tool by name."""
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}")
    return TOOL_REGISTRY[name]
```

**Step 5: Create `src/ast_tools/utils/__init__.py`**
```python
"""AST-Tools: Shared utilities."""
```

**Step 6: Verify package structure**
```bash
python3 -c "from ast_tools import server; print('OK')"
```

**Step 7: Commit**
```bash
git add -A && git commit -m "refactor: create modular package structure"
```

---

### Task 1.2: Extract Annotation Utilities

**Objective:** Move AST annotation helpers to `src/ast_tools/utils/annotations.py`.

**Files:**
- Create: `src/ast_tools/utils/annotations.py`

**Step 1: Find annotation-related code in ast_tools_server.py**
```bash
cd ~/Workspaces/ast-tools
grep -n "def.*signature\|def.*annotation\|libcst.*ann" src/ast_tools_server.py | head -20
```

**Step 2: Extract to `src/ast_tools/utils/annotations.py`**
(Full implementation — copy exact code from server.py lines containing annotation helpers)

**Step 3: Update server.py import**
```python
from .utils.annotations import function_signature, class_signature
```

**Step 4: Verify**
```bash
python3 -m pytest tests/test_e2e.py::TestMCPServer::test_list_tools -v
```

**Step 5: Commit**
```bash
git add -A && git commit -m "refactor: extract annotation utilities"
```

---

### Task 1.3: Extract Cache Utilities (Prep for Semantic DB)

**Objective:** Create content-hash caching utilities in `src/ast_tools/utils/cache.py`.

**Files:**
- Create: `src/ast_tools/utils/cache.py`

**Code:**
```python
"""Content-hash based caching for AST analysis."""

import hashlib
from pathlib import Path
from typing import Any, Optional

class FileCache:
    """Cache file contents with hash-based invalidation (Serena pattern)."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "ast-tools"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple[str, Any]] = {}  # path -> (hash, data)
    
    def _compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get_or_compute(self, file_path: str, compute_fn: callable) -> Any:
        """Get cached result or compute and cache it."""
        path = Path(file_path)
        if not path.exists():
            return None
        
        content = path.read_text()
        content_hash = self._compute_hash(content)
        
        if file_path in self._cache:
            cached_hash, cached_data = self._cache[file_path]
            if cached_hash == content_hash:
                return cached_data
        
        # Compute and cache
        data = compute_fn(content)
        self._cache[file_path] = (content_hash, data)
        return data
    
    def invalidate(self, file_path: str):
        """Invalidate cache for a file."""
        if file_path in self._cache:
            del self._cache[file_path]
    
    def clear(self):
        """Clear entire cache."""
        self._cache.clear()
```

**Step 2: Wire into server.py**
```python
from .utils.cache import FileCache
_global_cache = FileCache()
```

**Step 3: Commit**
```bash
git add -A && git commit -m "feat: add content-hash cache utilities"
```

---

## Phase 2: Extract Simple Tools

**Objective:** Extract standalone tools that don't depend on complex shared state.

### Task 2.1: Extract `codebase_summary` Tool

**Files:**
- Create: `src/ast_tools/tools/codebase_summary.py`
- Modify: `src/ast_tools/tools/__init__.py`

**Step 1: Copy tool code from server.py**
(Find `_tool_codebase_summary` function and copy to new file)

**Step 2: Register in `tools/__init__.py`**
```python
from .codebase_summary import _tool_codebase_summary as codebase_summary_handler
register_tool("codebase_summary", codebase_summary_handler)
```

**Step 3: Verify**
```bash
python3 -m pytest tests/test_e2e.py::TestMCPServer::test_list_tools -v
```

**Step 4: Commit**
```bash
git commit -am "refactor: extract codebase_summary tool"
```

---

### Task 2.2: Extract `project_info` Tool

(Same pattern as Task 2.1)

---

### Task 2.3: Extract `ast_generate_stub` Tool

(Same pattern — uses annotation utilities from Phase 1)

---

## Phase 3: Extract Core Tools

**Objective:** Extract the heavily-used core tools: `ast_read`, `ast_edit`, `ast_grep`.

### Task 3.1: Extract `ast_read` Tool

**Files:**
- Create: `src/ast_tools/tools/ast_read.py`

**Special handling:**
- Uses `_should_include()` helper (from annotation utils)
- Uses cache utilities
- Register in `tools/__init__.py`

---

### Task 3.2: Extract `ast_edit` Tool

**Files:**
- Create: `src/ast_tools/tools/ast_edit.py`

**Special handling:**
- Uses libcst directly
- No special dependencies

---

### Task 3.3: Extract `ast_grep` Tool

**Files:**
- Create: `src/ast_tools/tools/ast_grep.py`

**Special handling:**
- Calls external `ast-grep` CLI
- Uses terminal for subprocess

---

## Phase 4: Extract Remaining Tools

Extract in parallel where independent:

### Task 4.1: Extract `ast_refactor_extract_interface`
(Move from `interface_extractor.py` to proper module)

### Task 4.2: Extract `structural_analysis`

### Task 4.3: Extract `find_references`

### Task 4.4: Extract `impact_analysis`

### Task 4.5: Extract `module_imports`

---

## Phase 5: Server Refactor + Tests

### Task 5.1: Refactor `ast_tools_server.py` to Entry Point Shim

**Files:**
- Modify: `src/ast_tools_server.py`

**Code:**
```python
#!/usr/bin/env python3
"""AST-Tools MCP Server — entry point shim for backward compatibility."""

from ast_tools.server import create_server

server = create_server()

if __name__ == "__main__":
    import asyncio
    from mcp.server.stdio import stdio_server
    
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    
    asyncio.run(main())
```

### Task 5.2: Update Test Imports

**Files:**
- Modify: `tests/test_e2e.py`

**Change:**
```python
# Before
from ast_tools_server import list_tools

# After
from ast_tools.server import list_tools
```

### Task 5.3: Run Full Test Suite

```bash
cd ~/Workspaces/ast-tools
python3 -m pytest tests/ -x -v --tb=short
```

### Task 5.4: Final Commit

```bash
git add -A && git commit -m "refactor: complete modular extraction (all 11 tools)"
```

---

## Verification Checklist

- [ ] All 114 tests pass
- [ ] No test modifications needed (backward compatible)
- [ ] Server starts: `python -m ast_tools_server`
- [ ] Lint passes: `ruff check src/ tests/`
- [ ] Type check: `pyright src/`
- [ ] Package installable: `pip install -e .`

---

## Rollback Plan

If any phase breaks:
```bash
git revert HEAD  # Undo last phase
# OR
git reset --hard HEAD~1  # Remove last commit entirely
```

Each phase is one commit = clean rollback.
---

## semantic-db-phase1-v1

# Semantic Database — Phase 1 Implementation Plan

**Version:** 1.0  
**Date:** 2026-06-23  
**Mode:** MEDIUM (plan-and-audit skill)  
**Spec Reference:** `docs/specs/semantic-db-phase1-v1.md`

---

## Overview

**Goal:** Build core indexer library with SQLite persistence, content-hash caching, and 5 new MCP tools.

**Execution Order:** Sequential phases (shared dependencies)

| Phase | Component | Files | Est. Time |
|-------|-----------|-------|-----------|
| **Phase 0** | Prerequisites | Install tree-sitter, create dirs | 5 min |
| **Phase 1** | Database Layer | `database/` (4 files) | 30 min |
| **Phase 2** | Indexer Core | `indexer/` (3 files) | 40 min |
| **Phase 3** | MCP Tools | `tools/` (5 files) | 40 min |
| **Phase 4** | Integration | Server wiring, tests | 30 min |

**Total:** ~2.5 hours (with TDD cycles)

---

## Phase 0: Prerequisites

### Task 0.1: Install tree-sitter Dependencies

**Objective:** Install tree-sitter Python bindings + language grammars.

**Step 1: Install via pip**
```bash
pip install tree-sitter tree-sitter-python tree-sitter-typescript
```

**Step 2: Verify installation**
```bash
python3 -c "import tree_sitter; import tree_sitter_python; print('OK')"
```

**Step 3: Commit**
```bash
git add -A && git commit -m "chore: install tree-sitter dependencies"
```

### Task 0.2: Create Package Directories

**Step 1: Create directories**
```bash
cd ~/Workspaces/ast-tools
mkdir -p src/ast_tools/indexer src/ast_tools/database
mkdir -p tests/indexer tests/database
```

**Step 2: Verify structure**
```bash
find src/ast_tools -type d | sort
```

---

## Phase 1: Database Layer

### Task 1.1: Database Connection Management

**File:** `src/ast_tools/database/connection.py` (NEW)

**Objective:** Create connection factory with WAL mode and proper pragmas.

**Implementation:**
```python
"""Database connection management."""

import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

DEFAULT_DB_PATH = Path.home() / ".cache" / "ast-tools" / "codebase.db"

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Create a connection with optimal pragmas."""
    db_path = db_path or DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Critical pragmas
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA busy_timeout = 5000")  # 5s timeout for locks
    
    return conn

@contextmanager
def database_context(db_path: Optional[Path] = None):
    """Context manager for database connections."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()
```

**Test:** `tests/database/test_connection.py::test_wal_mode_enabled`

---

### Task 1.2: Database Schema + Migrations

**File:** `src/ast_tools/database/schema.py` (NEW)

**Objective:** Define schema with versioning and auto-migration.

**Implementation:**
```python
"""Database schema definition and migrations."""

import sqlite3
from pathlib import Path
from typing import List, Tuple

SCHEMA_VERSION = 1

INITIAL_SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

-- Core symbols table
CREATE TABLE IF NOT EXISTS symbols (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('function','class','method','variable','import','constant')),
    file_path TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    signature TEXT,
    docstring TEXT,
    is_public INTEGER DEFAULT 1,
    content_hash TEXT NOT NULL,
    indexed_at INTEGER NOT NULL
);

-- FTS5 for fast name/search
CREATE VIRTUAL TABLE symbols_fts USING fts5(
    name, signature, docstring,
    content=''
);

-- Edges (calls, imports, inherits)
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT REFERENCES symbols(id),
    target_name TEXT NOT NULL,
    target_id TEXT REFERENCES symbols(id),
    edge_type TEXT CHECK(edge_type IN ('calls','imports','inherits','instantiates')),
    resolution_state INTEGER DEFAULT 0,
    UNIQUE(source_id, target_name, edge_type)
);

-- File cache (content-hash tracking)
CREATE TABLE IF NOT EXISTS file_cache (
    file_path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    last_indexed INTEGER NOT NULL,
    symbol_count INTEGER DEFAULT 0
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_qualified ON symbols(qualified_name);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_file_cache_hash ON file_cache(content_hash);

-- Triggers for FTS5 sync
CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, signature, docstring)
    VALUES (NEW.rowid, NEW.name, NEW.signature, NEW.docstring);
END;

CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, signature, docstring)
    VALUES ('delete', OLD.rowid, OLD.name, OLD.signature, OLD.docstring);
END;

CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, signature, docstring)
    VALUES ('delete', OLD.rowid, OLD.name, OLD.signature, OLD.docstring);
    INSERT INTO symbols_fts(rowid, name, signature, docstring)
    VALUES (NEW.rowid, NEW.name, NEW.signature, NEW.docstring);
END;
"""

def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema."""
    conn.executescript(INITIAL_SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, int(Path.now().timestamp()))
    )
    conn.commit()

def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version."""
    row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    return row['version'] if row else 0

def needs_migration(conn: sqlite3.Connection) -> bool:
    """Check if migration is needed."""
    return get_schema_version(conn) < SCHEMA_VERSION
```

**Test:** `tests/database/test_schema.py::test_initial_schema_created`

---

### Task 1.3: Query Functions

**File:** `src/ast_tools/database/queries.py` (NEW)

**Objective:** Implement all database query operations.

**Implementation (partial — full file ~400 lines):**
```python
"""Database query functions."""

import sqlite3
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class Symbol:
    id: str
    name: str
    qualified_name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    signature: Optional[str]
    docstring: Optional[str]
    is_public: bool
    content_hash: str

def search_symbols(
    conn: sqlite3.Connection,
    query: str,
    kind: Optional[str] = None,
    limit: int = 20
) -> List[Symbol]:
    """Search symbols using FTS5 + BM25 ranking."""
    sql = """
        SELECT s.* FROM symbols s
        JOIN symbols_fts fts ON s.rowid = fts.rowid
        WHERE fts MATCH ?
        {kind_filter}
        ORDER BY bm25(symbols_fts)
        LIMIT ?
    """
    
    kind_filter = "AND s.kind = ?" if kind else ""
    params = [query] + ([kind] if kind else []) + [limit]
    
    rows = conn.execute(sql.format(kind_filter=kind_filter), params).fetchall()
    return [Symbol(**dict(row)) for row in rows]

def find_symbol_definition(
    conn: sqlite3.Connection,
    name: str
) -> Optional[Symbol]:
    """Find exact symbol definition by name."""
    row = conn.execute(
        "SELECT * FROM symbols WHERE name = ? OR qualified_name = ? LIMIT 1",
        (name, name)
    ).fetchone()
    return Symbol(**dict(row)) if row else None

def list_symbols_by_file(
    conn: sqlite3.Connection,
    file_path: str
) -> List[Symbol]:
    """List all symbols in a file."""
    rows = conn.execute(
        "SELECT * FROM symbols WHERE file_path = ? ORDER BY start_line",
        (file_path,)
    ).fetchall()
    return [Symbol(**dict(row)) for row in rows]

def get_cached_hash(
    conn: sqlite3.Connection,
    file_path: str
) -> Optional[str]:
    """Get cached content hash for a file."""
    row = conn.execute(
        "SELECT content_hash FROM file_cache WHERE file_path = ?",
        (file_path,)
    ).fetchone()
    return row['content_hash'] if row else None

def update_file_cache(
    conn: sqlite3.Connection,
    file_path: str,
    content_hash: str,
    symbol_count: int
) -> None:
    """Update file cache entry."""
    conn.execute("""
        INSERT OR REPLACE INTO file_cache (file_path, content_hash, last_indexed, symbol_count)
        VALUES (?, ?, strftime('%s', 'now'), ?)
    """, (file_path, content_hash, symbol_count))
    conn.commit()

def insert_symbol(
    conn: sqlite3.Connection,
    symbol: Symbol
) -> None:
    """Insert or update a symbol."""
    conn.execute("""
        INSERT OR REPLACE INTO symbols 
        (id, name, qualified_name, kind, file_path, start_line, end_line, 
         signature, docstring, is_public, content_hash, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%s', 'now'))
    """, (symbol.id, symbol.name, symbol.qualified_name, symbol.kind,
          symbol.file_path, symbol.start_line, symbol.end_line,
          symbol.signature, symbol.docstring, symbol.is_public, symbol.content_hash))
    conn.commit()

def insert_edge(
    conn: sqlite3.Connection,
    source_id: str,
    target_name: str,
    edge_type: str,
    target_id: Optional[str] = None
) -> None:
    """Insert an edge (call, import, inherit)."""
    conn.execute("""
        INSERT OR REPLACE INTO edges (source_id, target_name, target_id, edge_type, resolution_state)
        VALUES (?, ?, ?, ?, ?)
    """, (source_id, target_name, target_id, edge_type, 1 if target_id else 0))
    conn.commit()
```

**Test:** `tests/database/test_queries.py::test_search_symbols_fts5`

---

### Task 1.4: Database Package Init

**File:** `src/ast_tools/database/__init__.py` (NEW)

```python
"""Database layer for semantic codebase index."""

from .connection import get_connection, database_context
from .schema import init_schema, get_schema_version, needs_migration
from .queries import (
    Symbol,
    search_symbols,
    find_symbol_definition,
    list_symbols_by_file,
    get_cached_hash,
    update_file_cache,
    insert_symbol,
    insert_edge,
)

__all__ = [
    'get_connection',
    'database_context',
    'init_schema',
    'get_schema_version',
    'needs_migration',
    'Symbol',
    'search_symbols',
    'find_symbol_definition',
    'list_symbols_by_file',
    'get_cached_hash',
    'update_file_cache',
    'insert_symbol',
    'insert_edge',
]
```

---

## Phase 2: Indexer Core

### Task 2.1: Parser Abstraction

**File:** `src/ast_tools/indexer/parser.py` (NEW)

**Objective:** Unified parser interface for Python `ast` + tree-sitter fallback.

**Implementation:**
```python
"""AST parser abstraction."""

import ast
from pathlib import Path
from typing import Optional, Any
import tree_sitter_python as tspython

class Parser:
    """Unified parser for Python code."""
    
    def __init__(self):
        self.ts_language = tspython.language()
    
    def parse_python_ast(self, source: str, filename: str = "<unknown>") -> ast.AST:
        """Parse Python code using stdlib ast module."""
        return ast.parse(source, filename=filename)
    
    def parse_tree_sitter(self, source: bytes) -> Any:
        """Parse using tree-sitter (for future multi-language support)."""
        from tree_sitter import Parser as TSParser
        ts_parser = TSParser()
        ts_parser.set_language(self.ts_language)
        return ts_parser.parse(source)
```

**Test:** `tests/indexer/test_parser.py::test_parse_python_ast`

---

### Task 2.2: Symbol Extractor

**File:** `src/ast_tools/indexer/extractor.py` (NEW)

**Objective:** Extract symbols and edges from parsed AST.

**Implementation (partial):**
```python
"""Symbol and edge extraction from AST."""

import ast
from pathlib import Path
from typing import List, Tuple
from ..database import Symbol

class SymbolExtractor(ast.NodeVisitor):
    """Extract symbols from Python AST."""
    
    def __init__(self, file_path: str, content_hash: str):
        self.file_path = file_path
        self.content_hash = content_hash
        self.symbols: List[Symbol] = []
        self.edges: List[Tuple[str, str, str]] = []  # (source_id, target_name, edge_type)
        self.scope: List[str] = []  # Qualified name stack
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        qualified_name = ".".join(self.scope + [node.name])
        symbol_id = f"{self.file_path}:{qualified_name}"
        
        signature = self._get_signature(node)
        docstring = ast.get_docstring(node)
        
        symbol = Symbol(
            id=symbol_id,
            name=node.name,
            qualified_name=qualified_name,
            kind="function",
            file_path=self.file_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            signature=signature,
            docstring=docstring,
            is_public=not node.name.startswith("_"),
            content_hash=self.content_hash
        )
        self.symbols.append(symbol)
        
        # Extract calls within function
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()
    
    def visit_ClassDef(self, node: ast.ClassDef):
        # Similar to FunctionDef
        pass
    
    def visit_Import(self, node: ast.Import):
        # Extract import edges
        pass
    
    def visit_Call(self, node: ast.Call):
        # Extract call edges
        if isinstance(node.func, ast.Name):
            self.edges.append((self._current_symbol_id(), node.func.id, "calls"))
        self.generic_visit(node)
    
    def _get_signature(self, node: ast.FunctionDef) -> str:
        """Generate function signature string."""
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)
        return f"def {node.name}({', '.join(args)})"
    
    def _current_symbol_id(self) -> Optional[str]:
        """Get current symbol ID from scope."""
        if self.scope:
            return f"{self.file_path}:{'.'.join(self.scope)}"
        return None

def extract_symbols(file_path: str, content: str, content_hash: str) -> Tuple[List[Symbol], List[Tuple]]:
    """Extract all symbols and edges from a Python file."""
    tree = ast.parse(content, filename=file_path)
    extractor = SymbolExtractor(file_path, content_hash)
    extractor.visit(tree)
    return extractor.symbols, extractor.edges
```

**Test:** `tests/indexer/test_extractor.py::test_extract_function_symbols`

---

### Task 2.3: Pickle Cache

**File:** `src/ast_tools/indexer/cache.py` (NEW)

**Objective:** Content-hash based AST caching with pickle.

**Implementation:**
```python
"""Pickle-based AST caching with content-hash invalidation."""

import hashlib
import pickle
from pathlib import Path
from typing import Optional, Any
import ast

CACHE_DIR = Path.home() / ".cache" / "ast-tools" / "ast-cache"

class ASTCache:
    """Content-hash based AST cache."""
    
    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def _compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_cache_path(self, file_path: str, content_hash: str) -> Path:
        """Generate cache file path."""
        safe_path = file_path.replace("/", "_").replace(":", "_")
        return CACHE_DIR / f"{safe_path}.{content_hash[:16]}.pkl"
    
    def get_or_parse(self, file_path: str, content: str) -> ast.AST:
        """Get cached AST or parse and cache."""
        content_hash = self._compute_hash(content)
        cache_path = self._get_cache_path(file_path, content_hash)
        
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except (pickle.PickleError, EOFError):
                cache_path.unlink()  # Corrupted cache
        
        # Parse and cache
        tree = ast.parse(content, filename=file_path)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(tree, f, protocol=pickle.HIGHEST_PROTOCOL)
        except (pickle.PickleError, OSError):
            pass  # Cache write failed, continue without caching
        
        return tree
    
    def invalidate(self, file_path: str):
        """Invalidate all cached ASTs for a file."""
        safe_path = file_path.replace("/", "_").replace(":", "_")
        for cache_file in CACHE_DIR.glob(f"{safe_path}.*.pkl"):
            cache_file.unlink()
```

**Test:** `tests/indexer/test_cache.py::test_cache_hit_on_unchanged_content`

---

### Task 2.4: Indexer Package Init

**File:** `src/ast_tools/indexer/__init__.py` (NEW)

```python
"""Indexer core for semantic codebase analysis."""

from .parser import Parser
from .extractor import SymbolExtractor, extract_symbols
from .cache import ASTCache

__all__ = [
    'Parser',
    'SymbolExtractor',
    'extract_symbols',
    'ASTCache',
]
```

---

## Phase 3: MCP Tools

### Task 3.1: search_symbols Tool

**File:** `src/ast_tools/tools/search_symbols.py` (NEW)

```python
"""MCP tool: search_symbols."""

from typing import Optional
from mcp.types import Tool

from ..database import get_connection, search_symbols as db_search_symbols

TOOL_DEFINITION = Tool(
    name="search_symbols",
    description="Search symbols by name/signature using FTS5 full-text search.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query (supports wildcards)"},
            "kind": {"type": "string", "enum": ["function", "class", "method", "variable", "import", "constant"], "description": "Filter by symbol kind"},
            "limit": {"type": "integer", "default": 20, "description": "Max results"}
        },
        "required": ["query"]
    }
)

async def search_symbols_handler(name: str, arguments: dict) -> list:
    """Handle search_symbols tool call."""
    query = arguments["query"]
    kind = arguments.get("kind")
    limit = arguments.get("limit", 20)
    
    with get_connection() as conn:
        results = db_search_symbols(conn, query, kind, limit)
    
    return [
        {
            "name": r.name,
            "qualified_name": r.qualified_name,
            "kind": r.kind,
            "file_path": r.file_path,
            "start_line": r.start_line,
            "signature": r.signature
        }
        for r in results
    ]
```

**Test:** `tests/tools/test_semantic_tools.py::test_search_symbols_mcp`

---

### Task 3.2: find_symbol_definition Tool

**File:** `src/ast_tools/tools/find_symbol_definition.py` (NEW)

(Pattern identical to Task 3.1, uses `find_symbol_definition` query)

---

### Task 3.3: list_symbols Tool

**File:** `src/ast_tools/tools/list_symbols.py` (NEW)

(Uses `list_symbols_by_file` query)

---

### Task 3.4: index_status Tool

**File:** `src/ast_tools/tools/index_status.py` (NEW)

```python
"""MCP tool: index_status."""

from mcp.types import Tool
from ..database import get_connection

TOOL_DEFINITION = Tool(
    name="index_status",
    description="Get index statistics: indexed file count, cache size, last update.",
    inputSchema={"type": "object", "properties": {}}
)

async def index_status_handler(name: str, arguments: dict) -> dict:
    """Handle index_status tool call."""
    with get_connection() as conn:
        file_count = conn.execute("SELECT COUNT(*) FROM file_cache").fetchone()[0]
        symbol_count = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    
    return {
        "indexed_files": file_count,
        "total_symbols": symbol_count,
        "total_edges": edge_count,
        "cache_path": str(Path.home() / ".cache" / "ast-tools")
    }
```

---

### Task 3.5: refresh_index Tool

**File:** `src/ast_tools/tools/refresh_index.py` (NEW)

```python
"""MCP tool: refresh_index."""

from pathlib import Path
from typing import Optional, List
from mcp.types import Tool
from ..database import get_connection
from ..indexer import extract_symbols, ASTCache

TOOL_DEFINITION = Tool(
    name="refresh_index",
    description="Force reindex files. If file_paths is None, reindex entire codebase.",
    inputSchema={
        "type": "object",
        "properties": {
            "file_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to reindex (None = all)"
            },
            "project_root": {
                "type": "string",
                "description": "Project root directory"
            }
        }
    }
)

async def refresh_index_handler(name: str, arguments: dict) -> dict:
    """Handle refresh_index tool call."""
    file_paths = arguments.get("file_paths")
    project_root = Path(arguments.get("project_root", "."))
    
    if not file_paths:
        # Scan project for Python files
        file_paths = [str(p) for p in project_root.glob("**/*.py") if "__pycache__" not in str(p)]
    
    cache = ASTCache()
    indexed = 0
    errors = []
    
    with get_connection() as conn:
        for file_path in file_paths:
            try:
                content = Path(file_path).read_text()
                # Compute hash
                import hashlib
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                
                # Check if changed
                cached_hash = None  # Implement get_cached_hash call
                if cached_hash == content_hash:
                    continue  # Unchanged, skip
                
                # Parse and extract
                symbols, edges = extract_symbols(file_path, content, content_hash)
                
                # Update DB
                for symbol in symbols:
                    # Implement insert_symbol call
                    pass
                for edge in edges:
                    # Implement insert_edge call
                    pass
                
                indexed += 1
            except Exception as e:
                errors.append({"file": file_path, "error": str(e)})
    
    return {"indexed": indexed, "errors": errors}
```

---

## Phase 4: Integration

### Task 4.1: Wire Tools into Server

**File:** `src/ast_tools/tools/__init__.py` (MODIFY)

Add imports and registrations for 5 new tools.

### Task 4.2: Write Unit Tests

Create test files per phase above. Run:
```bash
PYTHONPATH=src python3 -m pytest tests/indexer/ tests/database/ -v
```

### Task 4.3: Write Integration Tests

```bash
PYTHONPATH=src python3 -m pytest tests/tools/test_semantic_tools.py -v
```

### Task 4.4: Run Full Test Suite

```bash
PYTHONPATH=src python3 -m pytest tests/ -x -q --tb=short
```

### Task 4.5: Final Commit

```bash
git add -A && git commit -m "feat: add semantic database core (Phase 1 complete)"
```

---

## Verification Checklist

- [ ] All new tests pass
- [ ] Existing 114 tests still pass
- [ ] 5 new MCP tools appear in `list_tools()`
- [ ] Database created at `~/.cache/ast-tools/codebase.db`
- [ ] FTS5 search returns results <50ms
- [ ] Incremental reindex skips unchanged files
- [ ] Pickle cache shows speedup on second parse

---

## Rollback Plan

Each phase is one commit. If Phase 1 fails:
```bash
git revert HEAD  # Undo Phase 1
```

---

**Next Step:** Dispatch forward + reverse audits before implementation.
---

## semantic-db-phase2-v2

# Semantic Database — Phase 2 Implementation Plan

**Version:** 2.0  
**Date:** 2026-07-23  
**Mode:** MEDIUM (plan-and-audit skill)  
**Spec Reference:** `docs/specs/semantic-db-phase2-v2.md`

---

## Overview

**Goal:** Add vector embeddings + semantic search to the existing Phase 1 semantic database.

**Execution Order:** Sequential phases (shared dependencies)

| Phase | Component | Files | Est. Time |
|-------|-----------|-------|-----------|
| **Phase 0** | Research | Subagent report | 10 min (parallel) |
| **Phase 1** | Spec | Interface contracts, schema ext | 15 min |
| **Phase 2** | Plan | Task breakdown (this file) | 10 min |
| **Phase 3** | Forward Audit | Validate feasibility | 5 min |
| **Phase 4** | Reverse Audit | Identify gaps/risks | 5 min |
| **Phase 5** | Synthesis | Final plan sign-off | 5 min |
| **Phase 6** | Install Deps | sentence-transformers, sqlite-vec | 5 min |
| **Phase 7** | Schema Migration | v1→v2, symbols_vec table | 20 min |
| **Phase 8** | Embedding Model | model.py, CPU inference | 30 min |
| **Phase 9** | Embedding Store | store.py, sqlite-vec integration | 25 min |
| **Phase 10** | Hybrid Search | semantic_search MCP tool | 30 min |
| **Phase 11** | Incremental Embed | extractor.py, cache.py patches | 20 min |
| **Phase 12** | Batch Backfill | refresh_index --embeddings | 15 min |
| **Phase 13** | Tests | 40+ new tests | 40 min |
| **Phase 14** | Adversarial Audit | Security, edge cases | 10 min |
| **Phase 15** | Lint + Dead Code | ruff, unused imports | 10 min |
| **Phase 16** | Docs | Phase 2 report, README updates | 15 min |
| **Phase 17** | Commit + Push | All phases, verify tests | 10 min |

**Total:** ~4.5 hours (with TDD cycles)

---

## Phase 6: Install Dependencies

### Task 6.1: Install Python Packages

**Command:**
```bash
cd ~/Workspaces/ast-tools
pip install sentence-transformers sqlite-vec
```

**Dependencies:**
- `sentence-transformers` — Transformer embedding API (wraps HuggingFace)
- `sqlite-vec` — SQLite vector similarity extension
- `torch` (auto) — PyTorch CPU backend (~100MB)

**Verify:**
```bash
python3 -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('bge-small-en-v1.5'); print('OK')"
python3 -c "import sqlite_vec; print('sqlite-vec version:', sqlite_vec.__version__)"
```

**Commit:**
```bash
git add -A && git commit -m "chore: install embedding dependencies (sentence-transformers, sqlite-vec)"
```

---

## Phase 7: Schema Migration (v1 → v2)

### Task 7.1: Extend Schema

**File:** `src/ast_tools/database/schema.py` (PATCH)

**Add to INITIAL_SCHEMA:**
```sql
-- Vector embeddings for semantic search (Phase 2)
CREATE VIRTUAL TABLE IF NOT EXISTS symbols_vec USING vec0(
    symbol_id TEXT PRIMARY KEY,
    embedding FLOAT[384]
);
```

**Add migration function:**
```python
def migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Migrate from schema v1 to v2 (add vector embeddings table)."""
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS symbols_vec USING vec0(
            symbol_id TEXT PRIMARY KEY,
            embedding FLOAT[384]
        )
    """)
    conn.commit()
```

**Update SCHEMA_VERSION:** `1 → 2`

**Test:** `tests/database/test_schema.py::test_migrate_v1_to_v2`

---

### Task 7.2: Update Schema Init

**File:** `src/ast_tools/database/schema.py` (PATCH)

**Modify `init_schema()`:**
```python
def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema."""
    conn.executescript(INITIAL_SCHEMA)
    
    # Run migrations if needed
    version = get_schema_version(conn)
    if version < 2:
        migrate_v1_to_v2(conn)
        update_schema_version(conn, 2)
    
    conn.commit()
```

**Test:** `tests/database/test_schema.py::test_init_schema_v2`

---

## Phase 8: Embedding Model

### Task 8.1: Create Model Module

**File:** `src/ast_tools/embeddings/model.py` (NEW)

**Implementation:**
```python
"""Transformer model for generating embeddings."""

from sentence_transformers import SentenceTransformer
from typing import Optional
import logging

logger = logging.getLogger(__name__)

MODEL_NAME = "bge-small-en-v1.5"
EMBEDDING_DIM = 384

_model: Optional[SentenceTransformer] = None

def get_model() -> SentenceTransformer:
    """Load or return cached model."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def generate_embedding(text: str, model: Optional[SentenceTransformer] = None) -> list[float]:
    """Generate embedding for text (docstring + signature)."""
    if model is None:
        model = get_model()
    embedding = model.encode([text], convert_to_numpy=True)[0]
    return embedding.tolist()

def generate_batch_embeddings(texts: list[str], model: Optional[SentenceTransformer] = None, batch_size: int = 32) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    if model is None:
        model = get_model()
    embeddings = model.encode(texts, batch_size=batch_size, convert_to_numpy=True)
    return embeddings.tolist()
```

**Test:** `tests/embeddings/test_model.py::test_generate_embedding`, `test_batch_embeddings`, `test_model_caching`

---

### Task 8.2: Create Embeddings Package Init

**File:** `src/ast_tools/embeddings/__init__.py` (NEW)

```python
"""Embeddings layer for semantic code search."""

from .model import get_model, generate_embedding, generate_batch_embeddings
from .store import insert_embedding, insert_embeddings_batch, search_similar

__all__ = [
    'get_model',
    'generate_embedding',
    'generate_batch_embeddings',
    'insert_embedding',
    'insert_embeddings_batch',
    'search_similar',
]
```

---

## Phase 9: Embedding Store (sqlite-vec)

### Task 9.1: Create Store Module

**File:** `src/ast_tools/embeddings/store.py` (NEW)

**Implementation:**
```python
"""sqlite-vec integration for vector storage and search."""

import sqlite3
from typing import List, Tuple, Optional
import sqlite_vec

def load_vec_extension(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension."""
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

def insert_embedding(conn: sqlite3.Connection, symbol_id: str, embedding: List[float]) -> None:
    """Insert or update embedding for a symbol."""
    embedding_bytes = bytes(embedding)  # Convert to BLOB
    conn.execute("""
        INSERT OR REPLACE INTO symbols_vec (symbol_id, embedding)
        VALUES (?, ?)
    """, (symbol_id, embedding_bytes))
    conn.commit()

def insert_embeddings_batch(conn: sqlite3.Connection, symbol_embeddings: List[Tuple[str, List[float]]]) -> None:
    """Batch insert embeddings."""
    data = [(sid, bytes(emb)) for sid, emb in symbol_embeddings]
    conn.executemany("""
        INSERT OR REPLACE INTO symbols_vec (symbol_id, embedding)
        VALUES (?, ?)
    """, data)
    conn.commit()

def search_similar(conn: sqlite3.Connection, query_embedding: List[float], k: int = 10) -> List[Tuple[str, float]]:
    """Find most similar symbols by cosine similarity."""
    query_bytes = bytes(query_embedding)
    rows = conn.execute("""
        SELECT symbol_id, distance 
        FROM symbols_vec 
        WHERE embedding MATCH ? 
        ORDER BY distance 
        LIMIT ?
    """, (query_bytes, k)).fetchall()
    return [(row['symbol_id'], row['distance']) for row in rows]
```

**Test:** `tests/embeddings/test_store.py::test_load_vec_extension`, `test_insert_embedding`, `test_search_similar`

---

### Task 9.2: Wire Extension Loading

**File:** `src/ast_tools/database/connection.py` (PATCH)

**Add to `get_connection()`:**
```python
from ast_tools.embeddings.store import load_vec_extension

# After creating connection
conn = get_connection(db_path)
load_vec_extension(conn)  # Load sqlite-vec
```

**Test:** Verify `symbols_vec` table accessible after connection

---

## Phase 10: Hybrid Search Tool

### Task 10.1: Create Semantic Search Tool

**File:** `src/ast_tools/tools/semantic_search.py` (NEW)

**Implementation:**
```python
"""MCP tool: hybrid semantic + keyword search."""

from mcp.server import Server
from ast_tools.database import get_connection
from ast_tools.embeddings import generate_embedding, search_similar
from typing import Optional

def hybrid_search(conn: sqlite3.Connection, query: str, k: int = 10, kind: Optional[str] = None) -> list[dict]:
    """Hybrid search: FTS5 + vector with RRF fusion."""
    
    # 1. Vector search
    query_emb = generate_embedding(query)
    vec_results = search_similar(conn, query_emb, k=k*2)
    
    # 2. FTS5 keyword search
    fts_sql = """
        SELECT s.rowid, bm25(symbols_fts) as score
        FROM symbols_fts
        WHERE symbols_fts MATCH ?
    """
    params = [query]
    if kind:
        fts_sql += " AND s.kind = ?"
        params.append(kind)
    fts_sql += " LIMIT ?"
    params.append(k * 2)
    
    fts_results = conn.execute(fts_sql, params).fetchall()
    
    # 3. Reciprocal Rank Fusion
    fused_scores = {}
    for i, (symbol_id, _) in enumerate(vec_results):
        fused_scores[symbol_id] = fused_scores.get(symbol_id, 0) + 1 / (i + 1 + 1.5)
    for row in fts_results:
        symbol_id = str(row['rowid'])  # FTS5 returns rowid, need to map
        fused_scores[symbol_id] = fused_scores.get(symbol_id, 0) + 1 / (row['score'] + 1 + 1.5)
    
    # 4. Sort by fused score
    top_k = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:k]
    
    # 5. Fetch full symbol details
    symbols = []
    for symbol_id, _ in top_k:
        symbol = conn.execute("SELECT * FROM symbols WHERE id = ?", (symbol_id,)).fetchone()
        if symbol:
            symbols.append(dict(symbol))
    
    return symbols

@mcp.tool()
async def semantic_search(query: str, k: int = 10, kind: Optional[str] = None) -> str:
    """Search symbols by semantic similarity (meaning) + keyword matching."""
    conn = get_connection()
    results = hybrid_search(conn, query, k, kind)
    return json.dumps(results, indent=2)
```

**Test:** `tests/tools/test_semantic_search.py::test_semantic_search_basic`, `test_hybrid_ranking`

---

### Task 10.2: Register Tool in Server

**File:** `src/ast_tools_server.py` (PATCH)

**Add to tool list:**
```python
@mcp.tool()
async def semantic_search(query: str, k: int = 10, kind: Optional[str] = None) -> str:
    """Search symbols by semantic similarity (meaning) + keyword matching."""
    ...
```

**Update `list_tools()`:** Add `semantic_search` to registry

---

## Phase 11: Incremental Embedding

### Task 11.1: Patch Extractor

**File:** `src/ast_tools/indexer/extractor.py` (PATCH)

**Add embedding generation to symbol creation:**
```python
from ast_tools.embeddings import generate_embedding

def create_symbol(...):
    symbol = Symbol(...)
    
    # Generate embedding (docstring + signature)
    embedding_text = f"{symbol.signature or ''} {symbol.docstring or ''}".strip()
    if embedding_text:
        symbol.embedding = generate_embedding(embedding_text)
    
    return symbol
```

---

### Task 11.2: Patch Cache

**File:** `src/ast_tools/indexer/cache.py` (PATCH)

**Add embedding hash tracking:**
```python
# In file_cache table, add embedding_hash column
# Check: if docstring_hash unchanged, skip embedding generation
```

---

## Phase 12: Batch Backfill

### Task 12.1: Add --embeddings Flag to refresh_index

**File:** `src/ast_tools/tools/refresh_index.py` (PATCH)

**Add CLI arg:**
```python
@click.option('--embeddings', is_flag=True, help='Generate embeddings for all symbols')
```

**Implement backfill:**
```python
if embeddings:
    model = get_model()
    symbols = conn.execute("SELECT id, signature, docstring FROM symbols").fetchall()
    
    batch = []
    for symbol in symbols:
        text = f"{symbol['signature'] or ''} {symbol['docstring'] or ''}".strip()
        if text:
            emb = generate_embedding(text, model)
            batch.append((symbol['id'], emb))
        
        if len(batch) >= 100:
            insert_embeddings_batch(conn, batch)
            batch = []
    
    if batch:
        insert_embeddings_batch(conn, batch)
```

---

## Phase 13: Tests

### Task 13.1: Create Test Files

**Files:**
- `tests/embeddings/test_model.py` (8 tests)
- `tests/embeddings/test_store.py` (10 tests)
- `tests/tools/test_semantic_search.py` (12 tests)

**Test patterns:**
- Model loading, CPU inference
- sqlite-vec insert/search
- Hybrid search ranking validation
- Incremental embedding (changed docstring → re-embed)

---

## Phase 14-17: Audit, Lint, Docs, Commit

Follow standard plan-and-audit workflow:
1. Forward + Reverse audits (parallel dispatch)
2. Synthesis + sign-off
3. Adversarial audit (security, edge cases)
4. Ruff lint + dead code removal
5. Phase 2 report
6. Commit all phases, push to master

---

## Dependencies Graph

```
Phase 6 (Install) → Phase 7 (Schema) → Phase 9 (Store) → Phase 10 (Search Tool)
                                    → Phase 8 (Model) ↗
                                    → Phase 11 (Incremental)
                                    → Phase 12 (Backfill)
                                    → Phase 13 (Tests)
```

---

**Next:** Phase 3-5 (Audits + Synthesis) → Phase 6 (Implementation kickoff)
