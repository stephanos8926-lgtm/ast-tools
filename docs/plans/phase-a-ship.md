# Phase A: Ship & Polish

**Effort:** ~6h
**Depends on:** Phase 7 (foundation)
**Blocks:** Phase D

## Tasks

| ID | Task | Effort | Status |
|----|------|--------|--------|
| A1 | Fix server venv + sync source to rapidwebs | 1h | ✅ DONE this session |
| A2 | Docs audit — fix pyproject name "ast-tools-mcp" across all .md files | 1h | 🔴 |
| A3 | Update release.yaml CI/CD URL to pypi.org/p/ast-tools-mcp | 0.5h | 🔴 |
| A4 | PyPI first publish (`uv build && uv publish --token $PYPI_TOKEN`) | 0.5h | 🔴 |
| A5 | README final OSS audit — verify no RapidWebs internals | 1h | ⚠️ Partial |
| A6 | Publish benchmark numbers | 2h | 🔴 |

## Rollback
A2-A4 are doc-only. A5 verifiable by grep for internal names. A6 is additive.
