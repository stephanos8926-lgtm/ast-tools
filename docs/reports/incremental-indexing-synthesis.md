# Synthesis: Incremental Indexing (Phase 8)

**Date:** 2026-06-30  
**Mode:** MEDIUM  
**Audits:** Forward + Reverse + Adversarial + Bug Review + Lint (inline)

---

## Audit Summary

| Audit | Verdict | Key Findings |
|-------|---------|--------------|
| **Forward** | ✅ GO | SQLite 3.46.1 ✅, existing tools confirmed ✅, schema supports diff ops ✅ |
| **Reverse** | ✅ GO | No blockers, existing file_cache table provides foundation ✅ |
| **Adversarial** | ✅ GO (with mitigations) | SQL injection: use parameterized queries ✅, Race conditions: use transactions ✅ |
| **Bug Review** | ✅ GO | No logic blockers, need to handle edge cases (empty files, renamed symbols) ✅ |
| **Lint** | ✅ GO | Project uses ruff with F401, E722, I001, ARG rules — new code must comply ✅ |

---

## Key Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Diff algorithm produces incorrect results | High | Extensive unit tests (10+ test cases), fallback to full reindex |
| Symbol ID instability | Medium | Match key = (file_path, qualified_name), preserve ID for unchanged |
| Performance regression | Low | Benchmark: incremental < 5s for 1-file change on 100-file project |
| Database corruption from race | Medium | SQLite transactions + WAL mode + retry decorator |
| Orphaned edges after symbol delete | Medium | Cascade delete: edges + embeddings in same transaction |

---

## Revised Plan Adjustments

Based on inline audit findings:

1. **No schema changes needed** — existing `symbols`, `edges`, `symbol_embeddings`, `file_cache` tables support incremental operations
2. **Add helper functions** — `delete_symbol_cascade()`, `update_symbol_fields()` (already done)
3. **Diff algorithm** — match by `(file_path, qualified_name)`, compare `signature + docstring` for "unchanged" detection
4. **Fallback** — if diff fails, fall back to full reindex for that file (existing behavior)
5. **Default mode** — `incremental=True` by default, `force=False` for backward compatibility

---

## Sign-off

**Spec:** ✅ Approved (based on inline audit)  
**Plan:** ✅ Approved  
**Risk level:** LOW — no schema changes, backward compatible, escape hatch available

**Ready for TDD implementation.**

---

## Implementation Phases

| Phase | Deliverable | Tests |
|-------|-------------|-------|
| 1 | `diff.py` — Symbol diff engine | 10 unit tests |
| 2 | `refresh_index.py` incremental path + helpers | 7 integration tests |
| 3 | `index_status.py` — Status tool | 3 unit tests |
| 4 | CLI `ast index` command | 4 CLI tests |
| 5 | Register tools + full test suite | All existing + new pass |

**Total estimated tests:** 21+ new tests  
**Total estimated code:** ~530 lines
