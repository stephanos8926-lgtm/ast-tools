# AST-Tools Planning Synthesis — Audit Findings & Corrections

**Date:** 2026-07-02
**Source:** Forward + Reverse audits of all 7 planning documents

## Audit Verdicts

| Document | Forward | Reverse | Status |
|----------|---------|---------|--------|
| ADR-0009 Reranker | Path errors, outdated RRF description | C3: No failure handling, C6: No tests | ⚠️ Needs fixes |
| ADR-0010 Governance | Accurate scope, realistic estimate | C1: No DB migration, C2: CLI conflicts | ⚠️ Needs fixes |
| ADR-0011 PyPI | Mostly done, minor name errors | C4: No backward compat, C5: Wrong CI/CD URL | ⚠️ Fix release.yaml |
| TOOLING_SPEC Master | Stale metrics, effort 3x low | C7: No server strategy | ⚠️ Needs major update |
| category-c-autofix | Path errors, 3x under-estimated | C6: Zero tests exist | 🔴 Redo effort estimate |
| category-deployment | ~15% done, docs paths wrong | C8: No aarch64 CI | ⚠️ Minor fixes |
| phase7-performance | 3/6 tasks ALREADY DONE | Accurate | ✅ Accurately scoped |

## Critical Corrections Applied

### 1. ADR-0009: Fix RRF Description & Path
- 6-factor RRF does NOT exist. Actual is 2-factor (FTS5 BM25 + vector cosine).
- `semantic_search.py` is at `src/ast_tools/tools/`, not `src/ast_tools/`.
- Add failure mode handling: offline, proxy, disk-full, rate-limit scenarios.
- Add model version pinning via revision hash.

### 2. ADR-0010: Add DB Migration & CLI Integration
- Schema versioning for governance tables (`migrations/` dir).
- CLI conflict resolution: `governance` as flat subcommand (no nested group) to match existing argparse.
- `ast init` already exists → governance init must be `ast governance init` via flat subcommand with prefix.
- Import graph infrastructure already exists (`module_imports.py`, `impact_analysis.py`, `transitive_analysis.py`) — leverage these.

### 3. ADR-0011 + CI/CD Fix
- `release.yaml` URL: `pypi.org/p/ast-tools` → `pypi.org/p/rw-ast-tools`
- Add backward compat note: no shim possible since old `ast-tools` is unrelated package. Document clearly.

### 4. Category C: Realistic Effort
- Auto-fix: 3-4 days (not 1)
- Reranker: 2-3 days (not 1) 
- Dashboard: 3-4 days (not 1)
- **Total: 8-11 days** (not 3-4)

### 5. Phase 7: Re-scoped
- 3/6 tasks already done → rename to "Phase 7 — Remaining Optimizations"
- Remaining: Task 3 (AST cache), Task 4 (connection pool), Task 5 (parallel tests)
- Revised: ~4h

## Revised Architecture

```
rw-ast-tools/ (PyPI name)
├── Phase 7: Remaining Opts (~4h) — AST cache, conn pool, parallel tests
├── Category A: Ship & Polish (~6h) — Server sync, docs audit, PyPI publish v0.1.0
├── Category B: Governance Engine (~6 days) 
│   ├── Phase B1: YAML schema + parser
│   ├── Phase B2: Scanner (leverage existing import graph)
│   ├── Phase B3: CLI integration
│   ├── Phase B4: Diff + baseline
│   └── Phase B5: HTML report
├── Category C: Killer Features (~8 days)
│   ├── Phase C1: Auto-fix pipeline (~3d)
│   ├── Phase C2: Reranker integration (~2d)
│   └── Phase C3: Architecture dashboard (~3d)
└── Category D: Launch (~3 days) — Onboarding, adapter, multi-arch, v0.2.0
```

**Total remaining effort:** ~18-20 days (revised from original optimistic 10-12)

**Execution order:** Phase 7 (foundation) → Category A (ship) → Category B (heavy hitter) → Category C (killer features) parallel with D prep → Category D (launch)
