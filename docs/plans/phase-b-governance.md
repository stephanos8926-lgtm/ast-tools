# Phase B: Architecture Governance Engine

**Effort:** 6 days
**Depends on:** Phase 7, Phase A (for tool count stability)
**Blocks:** Phase C3 (dashboard reads governance data)

## Tasks

| ID | Task | Effort | Status |
|----|------|--------|--------|
| B1 | YAML Schema + Validator (`governance.yaml` format, tag/layer system) | 1 day | 🔴 |
| B2 | Scanner — reverse-engineer import graph, compare to intended rules | 2 days | 🔴 |
| B3 | CLI — `ast governance {check,diff,report,init,baseline}` | 2 days | 🔴 |
| B4 | Governance diff between branches/commits | 1 day | 🔴 |

## Key Design Decisions
- Flat subcommands on existing CLI (no nested argparse groups)
- Leverage existing `module_imports.py`, `impact_analysis.py`, `transitive_analysis.py`
- Schema versioning in DB: add `schema_version` to governance tables
- No new DB tables initially — scan from existing import graph + YAML rules
