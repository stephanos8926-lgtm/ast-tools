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