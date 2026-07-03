# Forward Audit: Planning Documents vs. Actual Codebase

**Date:** 2026-07-02
**Auditor:** Lucien (Lead Digital Architect)
**Scope:** All 7 planning documents in `docs/adrs/`, `docs/specs/`, `docs/plans/`

---

## 1. ADR-0009: Reranker Integration

| Check | Finding |
|-------|---------|
| **Status** | Draft — **NOT implemented** |
| **Does feature exist?** | **No.** No reranker code exists anywhere in the codebase. |
| **File paths correct?** | **Partially.** ADR claims `src/ast_tools/semantic_search.py` but actual path is `src/ast_tools/tools/semantic_search.py`. ADR claims `src/ast_tools/reranker/` — directory does not exist. |
| **Interface contracts consistent?** | **No.** The actual `_tool_semantic_search` (line 291) has no `use_reranker` param. The existing search uses FTS5 keyword + vector semantic hybrid with RRF fusion (`RRF_K=1.5`), NOT the 6-factor RRF described in the ADR (no recency, usage, kind, proximity, or call-graph centrality factors). |
| **Already implemented?** | **No.** `tests/test_reranker.py`, `src/ast_tools/reranker/`, any `CrossEncoder` references — none exist. |
| **Effort estimate realistic?** | Category C claims 3-4 days for auto-fix + reranker + dashboard. Reranker alone requires: new module, model integration, RRF extension, tests. Realistic standalone: ~2-3 days. Combined with other C features: optimistic. |

**Verdict: PLANNING ONLY — zero code exists.**

---

## 2. ADR-0010: Architecture Governance Engine

| Check | Finding |
|-------|---------|
| **Status** | Proposed — **NOT implemented** |
| **Does feature exist?** | **No.** Directory `src/ast_tools/governance/` does not exist. No `governance.yaml` anywhere. No `ast governance` CLI commands. |
| **File paths correct?** | ADR proposes `src/ast_tools/governance/` with dsl_parser.py, violation.py, scanner.py, report.py, and cli.py. None exist. |
| **Interface contracts consistent?** | N/A — no contracts implemented. The actual CLI (`cli.py`) has commands for search, navigate, blast-radius, find-dead, summary, symbols, refs, init, doctor, vacuum, curator, cleanup but zero governance subcommands. |
| **Already implemented?** | **No.** Nothing exists. |
| **Effort estimate realistic?** | ADR claims 8 days total (Phase 1-5: 2+2+2+1+1 days). Category B claims 5-7 days. The project already has import graph building tools (`module_imports.py`, `transitive_analysis.py`, `impact_analysis.py`) that could be leveraged. Estimate is plausible if reusing these. |

**Verdict: PLANNING ONLY — zero code exists.**

---

## 3. ADR-0011: PyPI Name Decision + Publishing Pipeline

| Check | Finding |
|-------|---------|
| **Status** | **Partially implemented** |
| **Does feature exist?** | **Partial.** `pyproject.toml` name is `ast-tools-mcp` ✅. `scripts/publish.sh` exists ✅. `.github/workflows/python-publish.yml` exists ✅. `docs/` has NOT been audited for name changes. |
| **File paths correct?** | ✅ `scripts/publish.sh` exists and matches the documented content. CLI entry points match `[project.scripts]` in pyproject.toml. |
| **Interface contracts consistent?** | Minor inconsistency: ADR line 125 says "CLI remains: ast" but `publish.sh` line 29 correctly says "CLI entry points remain: ast-tools, ast-tools-server, ast-tools-project". The ADR text is wrong. |
| **Already implemented?** | Partially: pyproject.toml ✅, publish.sh ✅, CI/CD ✅. Not done: `README.md` still references "ast-tools" not "ast-tools-mcp"; `docs/` haven't been updated; no PyPI registration yet. |
| **Effort estimate realistic?** | Category A claims 1-2 days. Name decision is made, pipeline scripts exist. Remaining work is docs audit + first publish (~a few hours). |

**Verdict: MOSTLY IMPLEMENTED — docs audit and first publish remain.**

---

## 4. TOOLING_SPEC.md (Master Spec)

| Check | Finding |
|-------|---------|
| **Stats accuracy** | Claims "55 tools, 330+ tests, 693 tests collected". Actual README says "43 tools, 307+ tests". `register_tool` count in `__init__.py` is ~58 but includes duplicates/aliases. **Stats are inflated.** |
| **Category A: Ship & Polish** | Name change partially done ✅. CI/CD publishing exists ✅. README rewrite done ✅. Performance benchmark (`phase9_benchmark.py`) exists ✅. Docs update NOT done ❌. |
| **Category B: Arch Governance (5-7 days)** | **NOTHING implemented.** 0% complete. |
| **Category C: Killer Features (3-4 days)** | **NOTHING implemented.** No `fix/` module, no reranker, no dashboard. 0% complete. |
| **Category D: Launch Prep (1-2 days)** | Parts of D3 (PyPI publish) exist ✅. D1 (onboarding) ❌, D2 (ast-grep adapter) ❌, D4 (multi-arch) ❌. |

**Verdict: STALE — stats are out of date, Categories B and C have zero implementation, Category D partially done.**

---

## 5. category-c-autofix-and-reporter.md

| Check | Finding |
|-------|---------|
| **Part 1: Auto-fix Pipeline** | **NOT implemented.** No `src/ast_tools/fix/` directory. No `FixEngine` class. No `ast fix` CLI command. No `pipeline.py`, `linters.py`, or `formatter.py`. |
| **Part 2: Architecture HTML Report** | **NOT implemented.** No `ast architecture-report` CLI command. No D3.js/Sigma.js code. No HTML generation. |
| **`code_validate_syntax` claim** | ✅ **Exists** — registered at line 585 of `tools/__init__.py`, implemented in `tools/code_validate.py`. |
| **File paths correct?** | Spec claims `ast_tools/fix/`, `ast_tools/search/reranker.py`, `ast_tools/dashboard/`. None exist. |
| **Already implemented?** | Only `code_validate_syntax` exists (the foundation). Everything else is speculative. |
| **Effort estimate realistic?** | Category C claims **3-4 days** for all three features (auto-fix + reranker + dashboard). Each feature is substantial:
  - Auto-fix: integration with ruff/black/prettier, AST modification pipeline, CLI integration, tests — ~3-4 days standalone
  - Reranker: model integration, lazy loading, RRF extension, tests — ~2-3 days
  - Dashboard: HTML generation, graph visualization, governance integration — ~3-4 days
  **Total: 8-11 days minimum. The 3-4 day estimate is unrealistic by ~3x.**

**Verdict: PLANNING ONLY — only `code_validate_syntax` exists. Effort estimate is ~3x too low.**

---

## 6. category-deployment-launch.md

| Check | Finding |
|-------|---------|
| **D1: Multi-Agent Onboarding** | **NOT implemented.** `docs/ONBOARDING.md` does not exist. However `docs/AST_TOOLS_QUICKSTART.md` and `hermes-plugins/docs/` provide some coverage but not per-agent format specified. |
| **D2: Ast-grep MCP Compat Adapter** | **NOT implemented.** No `src/ast_tools/adapters/` directory. No `ast_grep_bridge.py`. However `tools/ast_grep.py` already wraps the ast-grep CLI directly (calls `ast-grep` subprocess). |
| **D3: PyPI Release v0.2.0** | **Partially implemented.** `python-publish.yml` exists ✅, `publish.sh` exists ✅. No actual PyPI release made yet. Version in pyproject.toml is 0.1.0, not 0.2.0. |
| **D4: Multi-Arch Build** | **NOT implemented.** No `Dockerfile` found. No multi-arch build configuration. pyproject.toml uses hatchling with no multi-arch settings. |
| **File paths correct?** | Spec says `docs/ONBOARDING.md` — doesn't exist. Spec says `src/ast_tools/adapters/ast_grep_bridge.py` — doesn't exist. |
| **Already implemented?** | D3 scripts are the only thing done. |
| **Effort estimate realistic?** | Category D claims 1-2 days. True if only D1 docs + D2 adapter. D4 multi-arch is more involved (Docker buildx, cross-compilation, testing on ARM). ~3-4 days total more realistic. |

**Verdict: MOSTLY PLANNING — only CI/CD scripts exist. No onboarding docs, no adapter, no multi-arch.**

---

## 7. phase7-performance-optimization.md

| Check | Finding |
|-------|---------|
| **Task 1: Lazy Embedding Model** | ✅ **ALREADY IMPLEMENTED.** `src/ast_tools/embeddings/model.py` uses `_model = None` global, loaded on first `get_model()` call, not at import. Follows the spec's recommendation exactly. |
| **Task 2: Incremental Index Default** | ✅ **ALREADY IMPLEMENTED.** `tools/refresh_index.py` has `incremental=True` default, `force=False`. SHA256 hash diff for change detection is present. The specific `schema_version` check mentioned in the plan is NOT present, but the core feature works. |
| **Task 3: AST Pattern Cache** | ❌ **NOT implemented.** `tools/ast_grep.py` has no `functools.lru_cache`, no pattern compilation caching, no `cache_stats` param. |
| **Task 4: Connection Caching** | ⚠️ **PARTIALLY implemented.** `database/connection.py` has `get_connection()` but creates a new connection each time. No `threading.local()`, no `get_cached_connection()`, no `close_cached_connections()`. |
| **Task 5: Parallel Test Suite** | ❌ **NOT implemented.** `pyproject.toml` has no `pytest-xdist` dependency. Pytest `addopts` is `-v --tb=short` only (no `-n auto`). |
| **Task 6: Token Budget Enforcement** | ✅ **ALREADY IMPLEMENTED.** `tools/semantic_search.py` has `token_budget` param (default 4096) and enforces it. Missing: `truncated` flag and `total_tokens` response metadata. |
| **Effort estimate realistic?** | Plan claims 8h total. 3 tasks (1, 2, 6) are already done (~3.5h saved). Remaining tasks (3, 4, 5) represent ~4h of work. **Estimate was accurate for original scope.** |

**Verdict: 3/6 tasks done, 1 partial, 2 not started. Plan was accurate; remaining effort ~4h.**

---

## Summary Matrix

| Document | Category | Implementation Status | File Path Accuracy | Effort Estimate |
|----------|----------|----------------------|-------------------|-----------------|
| ADR-0009 Reranker | Feature Spec | **0%** — nothing exists | ❌ Wrong path for semantic_search | Too low (bundled) |
| ADR-0010 Governance | Architecture | **0%** — nothing exists | N/A (proposed) | Plausible (~5-7d) |
| ADR-0011 PyPI/Publish | Release | **~70%** — core scripts done | ✅ Good | Realistic |
| TOOLING_SPEC Master | Meta | **~10% overall** — A partial, B+C=0%, D partial | ❌ Many nonexistent paths | B+C estimates ~3x low |
| category-c-autofix | Feature Spec | **~5%** — only code_validate_syntax | ❌ Nonexistent paths | **~3x too low** (8-11d vs 3-4d) |
| category-deployment | Release Plan | **~15%** — CI/CD scripts only | ❌ ONBOARDING.md, adapter paths missing | Slightly low (~3-4d vs 1-2d) |
| phase7-performance | Optimization | **~55%** — 3/6 done, 1 partial | ✅ Generally accurate | **Accurate** (8h original) |

### Key Issues Identified

1. **Stale metrics**: TOOLING_SPEC claims "55 tools, 330+ tests, 693 tests collected" — actual is ~43 tools, ~307 tests
2. **Wrong file paths**: ADR-0009 claims `src/ast_tools/semantic_search.py` — actual is `src/ast_tools/tools/semantic_search.py`; also claims reranker module doesn't exist
3. **Severely underestimated effort**: Category C claims 3-4 days for what would be 8-11 days of work
4. **Outdated search description**: ADR-0009 describes a "6-factor RRF" that doesn't exist — actual implementation is 2-factor (FTS5 + vector similarity)
5. **Inconsistent CLI name**: ADR-0011 says "CLI remains: ast" but actual CLI entry points are "ast-tools", "ast-tools-server", "ast-tools-project"
6. **Version mismatch**: Launch plan says v0.2.0 but pyproject.toml has 0.1.0
7. **Phase 7 already mostly done**: 3 of 6 optimization tasks are already implemented, plan doesn't reflect this

### Recommendations

1. **Update TOOLING_SPEC.md** with accurate tool count (43, not 55) and test count (~307, not 330+/693)
2. **Correct ADR-0009** to remove/update the inaccurate 6-factor RRF description and fix `semantic_search.py` path
3. **Recategorize Phase 7** as "Remaining Optimizations" since 3/6 tasks are already done
4. **Re-estimate Category C** realistically at 8-11 days (not 3-4)
5. **Create missing docs directory** (`docs/specs/audits/` already exists — this report lives here) and ensure `docs/ONBOARDING.md` path consistency
6. **Mark ADR-0009 and ADR-0010** clearly as "Draft/Proposed — Not Implemented" in the project tracking system
