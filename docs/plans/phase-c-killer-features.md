# Phase C: Killer Features

**Effort:** 8 days total (revised from 3-4 — original was 3x under-estimated)
**Depends on:** Phase 7 (for perf baseline), Phase B for C3 (dashboard reads governance)
**Independent sub-phases:** C1 and C2 can run in parallel

## Tasks

| ID | Task | Effort | Status |
|----|------|--------|--------|
| C1 | Auto-fix pipeline (`ast fix` command) | 3 days | 🔴 |
| C2 | Cross-encoder reranker integration | 2 days | 🔴 |
| C3 | Architecture HTML dashboard (D3/Sigma graph) | 3 days | 🔴 |

### C1 — Auto-fix Pipeline
- `src/ast_tools/fix/FixEngine` — orchestrator
- `ast fix [file]` — validate → lint → fix → reformat
- `ast fix --check` — CI mode (validate only)
- `ast fix --diff` — show proposed changes
- Integrate: code_validate_syntax, ruff --fix, gofmt, prettier

### C2 — Cross-encoder Reranker
- `src/ast_tools/reranker/CrossEncoder` wrapper (lazy loaded)
- Integrate into semantic_search post-RRF
- `use_reranker` param (default: false)
- Failure mode handling: offline, proxy, HF unavailable → graceful fallback to RRF-only

### C3 — Architecture Dashboard
- Standalone HTML report (single file, zero deps)
- D3 force-directed graph of imports
- Red highlights for governance violations (reads from Phase B)
- Export: `ast architecture-report [--output report.html]`
