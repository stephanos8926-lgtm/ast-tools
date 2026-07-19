# Audit Synthesis v3: Forward + Reverse + Adversarial Findings

> **Version:** v3  
> **Date:** 2026-07-14  
> **Author:** Lucien (Lead Digital Architect)  
> **Status:** Final  

---

## 1. Scope

This synthesis merges findings from three independent audits into a unified risk map, prioritization matrix, and actionable mitigation path.

| Audit | Source | Key Focus |
|-------|--------|-----------|
| **Forward Audit** | `audits/forward-audit-comprehensive.md` | Spec-to-code alignment, file path accuracy, effort estimation |
| **Reverse Audit** | `audits/reverse-audit-comprehensive.md` | Missing scope, dependency chains, cross-feature conflicts |
| **Adversarial Audit** | `audits/adversarial-trust-v2.md` | Trust boundary bypasses, anomaly scorer evasion, MCP registrar enforcement |

---

## 2. Cross-Cutting Risk Matrix

### 2.1 Critical (🔴) — Immediate Blockers

| ID | Finding | Forward | Reverse | Adversarial | Domain |
|----|---------|---------|---------|-------------|--------|
| **C1** | No DB schema migration or rollback strategy | — | 🔴 C1 | — | Governance |
| **C2** | Governance CLI conflicts with existing `ast init` | — | 🔴 C2 | — | CLI Architecture |
| **C3** | Reranker model download: zero failure mode handling | — | 🔴 C3 | — | Reranker |
| **C4** | No backward compatibility path for old PyPI name | — | 🔴 C4 | — | Publishing |
| **C5** | `release.yaml` points to wrong PyPI URL (`ast-tools` vs `rw-ast-tools`) | ✅ Forward A11 | 🔴 C5 | — | CI/CD |
| **C6** | Zero tests exist for any planned feature (reranker, governance, autofix, dashboard) | ✅ Forward A4 | 🔴 C6 | — | Testing |
| **C7** | No server sync/deployment strategy | — | 🔴 C7 | — | DevOps |
| **C8** | No aarch64 CI matrix | — | 🔴 C8 | — | Multi-Arch |
| **C9** | MCP Registrar: `ToolInfo` dataclass missing `trust`/`provenance` fields | — | — | 🔴 #3 | Trust |
| **C10** | AnomalyScorer signal bypass: crafted payload evades all 4 signals | — | — | 🟠 #1 | Trust |

### 2.2 High (🟠) — Must-Fix Before Release

| ID | Finding | Forward | Reverse | Adversarial | Domain |
|----|---------|---------|---------|-------------|--------|
| **H1** | Governance scanner duplicates existing `dependencies.graph` | — | 🟠 H1 | — | Governance |
| **H2** | Autofix pipeline: no handling for missing external tools | — | 🟠 H2 | — | Autofix |
| **H3** | `governance.yaml` fallback ambiguity (error vs proceed) | — | 🟠 H3 | — | Governance |
| **H4** | `sentence-transformers` in `[dependencies]` (not optional) — 1GB for all users | — | 🟠 H4 | — | Dependencies |
| **H5** | Release workflow missing pre-publish validation | — | 🟠 H5 | — | CI/CD |
| **H6** | Reranker + token budget interaction unspecified (ordering) | — | 🟠 H6 | — | Reranker |
| **H7** | No dependency pinning / `uv.lock` for reproducible builds | — | 🟠 H7 | — | Publishing |
| **H8** | No test fixture isolation for parallel pytest-xdist runs | — | 🟠 H8 | — | Testing |
| **H9** | LLM can disregard `TrustLevel` metadata (advisory-only enforcement) | — | — | 🟠 #2 | Trust |
| **H10** | `@file` injection can gain `VALIDATED` trust through anomaly scorer bypass | — | — | 🟡 #5 | Trust |
| **H11** | Cross-turn `additional_kwargs` loss risk during serialization | — | — | 🟡 #4 | Trust |

### 2.3 Medium (🟡) — Plan and Address

| ID | Finding | Forward | Reverse | Adversarial | Domain |
|----|---------|---------|---------|-------------|--------|
| **M1** | Governance diff duplicates existing co-change analysis | — | 🟡 M1 | — | Governance |
| **M2** | Architecture dashboard vs governance scanner: two divergent import graphs | — | 🟡 M2 | — | Architecture |
| **M3** | `publish.sh` partial failure: orphaned `dist/` artifacts | — | 🟡 M3 | — | Publishing |
| **M4** | Reranker timeout value undefined | — | 🟡 M4 | — | Reranker |
| **M5** | Token budget not user-configurable (CLI arg / config file) | — | 🟡 M5 | — | Configuration |
| **M6** | Category A acceptance criteria underspecified | — | 🟡 M6 | — | Benchmarking |
| **M7** | CHANGELOG strategy undefined | — | 🟡 M7 | — | Release |
| **M8** | TOOLING_SPEC stats inflated (55 tools → ~43, 693 tests → ~307) | ✅ F1 | — | — | Documentation |
| **M9** | ADR-0009 wrong file path & outdated 6-factor RRF description | ✅ F2, F4 | — | — | Documentation |
| **M10** | ADR-0011 CLI name inconsistency ("ast" vs "ast-tools") | ✅ F5 | — | — | Documentation |
| **M11** | Version mismatch: launch plan says v0.2.0, pyproject.toml has 0.1.0 | ✅ F6 | — | — | Release |
| **M12** | Tool name semantic injection (near-miss names bypass blocklist) | — | — | 🟡 #6 | Trust |

### 2.4 Low (🟢) — Polish and Monitor

| ID | Finding | Forward | Reverse | Adversarial | Domain |
|----|---------|---------|---------|-------------|--------|
| **L1** | No CI caching for HuggingFace model downloads | — | 🟢 L1 | — | CI |
| **L2** | No adapter tests for ast-grep bridge | — | 🟢 L4 | — | Testing |
| **L3** | No Docker multi-stage build | — | 🟢 L5 | — | Docker |
| **L4** | Entropy/length signals: false positive risk for legitimate data | — | — | 🔵 #7 | Trust |

---

## 3. Dependency Chain Analysis

### 3.1 Feature Dependency Graph

```
Governance Engine (C2, H1, M1)
  ├── depends on: DB schema migration (C1)
  ├── depends on: CLI integration plan (C2)
  └── conflicts with: existing `ast init` command (C2)

Reranker Integration (C3, H4, H6, M4)
  ├── depends on: optional dependency split (H4)
  ├── depends on: model download failure handling (C3)
  ├── interacts with: token budget enforcement (H6)
  └── blocked by: sentence-transformers not optional (H4)

Autofix Pipeline (H2)
  ├── depends on: external tool detection (H2)
  └── blocked by: no fixture isolation for parallel tests (H8)

Architecture Dashboard (M2)
  └── depends on: single-sourced import graph (H1, M2)

PyPI Release (C4, C5, H5, H7, M3, M7)
  ├── blocked by: wrong CI URL (C5)
  ├── blocked by: no backward compat for old name (C4)
  ├── blocked by: no pre-publish validation (H5)
  └── blocked by: no lockfile for reproducible builds (H7)

Trust Boundary System (C9, H9, H10, H11, M12, L4)
  ├── depends on: ToolInfo trust/provenance fields (C9)
  ├── depends on: stronger TrustLevel enforcement (H9)
  ├── depends on: cross-turn serialization tests (H11)
  └── blocked by: @file VALIDATED trust level design (H10)

Server Deployment (C7, C8)
  ├── depends on: deployment spec (C7)
  └── depends on: aarch64 CI matrix (C8)
```

### 3.2 Build Order (Recommended Execution Sequence)

| Phase | Items | Rationale |
|-------|-------|-----------|
| **P0 — Infrastructure** | C1 (DB migration), C9 (ToolInfo trust), C5 (CI URL fix) | Unblock everything else |
| **P1 — Trust Hardening** | C9 (ToolInfo), H9 (TrustLevel enforcement), H11 (serialization), H10 (@file VALIDATED redesign) | Security-critical, enables safe MCP tool registration |
| **P2 — Governance Foundation** | C2 (CLI plan), H1 (single import graph), M1 (reuse co-change), H3 (governance.yaml behavior) | Core governance engine |
| **P3 — Reranker** | H4 (optional deps), C3 (failure handling), H6 (token budget order), M4 (timeout) | Reranker feature |
| **P4 — CI/CD Quality** | C8 (aarch64), H5 (pre-publish), H7 (lockfile), H8 (parallel test isolation), L1 (CI caching) | Release pipeline |
| **P5 — Autofix + Dashboard** | H2 (external tool handling), M2 (single import graph) | Feature builds |
| **P6 — Release** | C4 (backward compat), C6 (test coverage), M3 (publish.sh), M7 (CHANGELOG), M11 (version sync) | Ship |
| **P7 — Polish** | M5 (token budget config), M6 (benchmark spec), M8 (stats accuracy), M9 (doc fixes), M10 (CLI name), L2 (adapter tests), L3 (multi-stage Docker) | Documentation and hardening |

---

## 4. Cross-Feature Conflict Matrix

| Feature A | Feature B | Conflict | Recommended Resolution |
|-----------|-----------|----------|----------------------|
| Governance scanner (`_build_import_graph`) | Existing `dependencies.graph` | Duplicate import graph | Governance scanner imports from `dependencies.graph` — do not reimplement |
| `ast governance init` | Existing `ast init` (setup wizard) | Name collision | Use `ast governance init-codebase` or nest under `ast governance check` |
| Reranker (`use_reranker=True`) | Token budget enforcement (phase7) | Truncation vs reranking order undefined | Token budget applies AFTER reranking — document in both specs |
| Parallel tests (`pytest-xdist`) | Governance/DB tests | Shared SQLite → lock contention | Per-test `tmp_path` fixtures + WAL journal mode |
| Dashboard (SQLite graph) | Governance scanner (live AST graph) | Two divergent import graphs | Single-source through `dependencies.graph` module |
| `ast fix` (autofix) | External linters (ruff, prettier) | Missing tool → crash | Graceful skip with actionable error messages |
| `@file` injection + `VALIDATED` trust | AnomalyScorer bypass | User file can gain verified status | Redesign `VALIDATED` — user files default to `USER_FILE` |

---

## 5. Trust Boundary Hardening Summary

### 5.1 Findings Consolidated from Adversarial Audit

| Threat | Severity | Current Defense | Gap | Mitigation |
|--------|----------|-----------------|-----|------------|
| AnomalyScorer signal bypass | 🟠 High | 4-signal weighted sum (pattern 40%, entropy 30%, length 20%, density 10%) | Each signal independently evadable; early exit at <0.3 skips scoring entirely | Adversarial testing, contextual detection, dynamic weighting |
| LLM disregards TrustLevel | 🟠 High | System prompt injection of trust metadata | LLM "helpfulness" bias may override metadata; purely advisory | Stronger prompt enforcement, pre-processing/redaction for high-anomaly content |
| MCP Registrar trust bypass | 🔴 Critical | `register_all.py` does NOT pass trust/provenance | ToolInfo dataclass missing trust/provenance fields | Add fields, enforce TOOL_EXTERNAL at registration |
| Cross-turn injection amplification | 🟡 Medium | Trust metadata in `additional_kwargs` survives | Only ToolMessage verified; AIMessage/HumanMessage untested | Explicit serialization for all message types + round-trip tests |
| @file VALIDATED trust elevation | 🟡 Medium | AnomalyScorer gates VALIDATED vs USER_FILE | User file can gain VALIDATED through bypass | Redesign: all user @file → USER_FILE default |
| Tool name semantic injection | 🟡 Medium | Regex + prefix blocklist | Near-miss names bypass string matching | Heuristic analysis, expanded blocklist |
| Entropy/length false positives | 🔵 Low | Weighted sum mitigates single-signal spikes | Per-tool config missing | Add per-tool signal weight configuration |

### 5.2 Trust Level Architecture (v3)

| Level | Value | Description | v3 Changes |
|-------|-------|-------------|------------|
| `SYSTEM` | 5 | System instructions | No change |
| `BUILTIN` | 4 | Built-in tool output | No change |
| `VALIDATED` | 4 | Project files verified by @file | **Redesigned**: only pre-vetted system files; user @file → USER_FILE |
| `USER_FILE` | 3 | User-provided file content | **New strict default** for all @file injections |
| `TOOL_INTERNAL` | 2 | Internal tool output | No change |
| `TOOL_EXTERNAL` | 1 | MCP tool output | **Enforced** at registration time via ToolInfo |
| `UNTRUSTED` | 0 | Unrecognized / fallback | No change |

---

## 6. Actionable Recommendation Summary

### 6.1 Immediate (Before Any Feature Work)

1. **Fix `release.yaml`** — Update PyPI URL from `ast-tools` to `rw-ast-tools` (C5)
2. **Add `trust`/`provenance` to `ToolInfo`** dataclass (C9)
3. **Move `sentence-transformers`** to `[project.optional-dependencies]` (H4)
4. **Define DB schema migration strategy** — Create `migrations/` directory + version protocol (C1)

### 6.2 Short-Term (Before First Release)

5. **Redesign `VALIDATED` trust level** — User @file → `USER_FILE` default (H10)
6. **Implement `register_mcp_tools()` trust enforcement** — Hardcode `TOOL_EXTERNAL` (C9)
7. **Add pre-publish validation** in release workflow (H5)
8. **Commit `uv.lock`** for reproducible builds (H7)
9. **Create CLI integration plan** for `ast governance` subcommands (C2)
10. **Write server deployment spec** (C7)

### 6.3 Medium-Term (Feature-Specific)

11. **Single-source import graph** through `dependencies.graph` (H1, M2)
12. **Add model download failure handling** — Retry, timeout, offline fallback (C3)
13. **Define token budget + reranker ordering** (H6)
14. **Add aarch64 CI matrix** (C8)
15. **Create shim package** `ast-tools → rw-ast-tools` for backward compat (C4)
16. **Write test fixture isolation** guidelines for parallel tests (H8)

### 6.4 Ongoing

17. **Adversarial testing** — Build adversarial example suite for AnomalyScorer
18. **Expand tool name blocklist** — Continuously update `_INJECTION_TOOL_NAMES` and `_RESERVED_PREFIXES`
19. **Per-tool anomaly scorer configuration** — Exempt known high-entropy tools
20. **Cross-turn trust serialization tests** — Verify round-trip for all message types

---

## 7. Forward Audit Gap Closure Status

| Forward Finding | Status | v3 Action |
|-----------------|--------|-----------|
| Stale metrics (55 tools, 693 tests) | ❌ Open | Update TOOLING_SPEC with actual: ~43 tools, ~307 tests |
| Wrong file paths (ADR-0009) | ❌ Open | Correct ADR-0009 paths and remove 6-factor RRF description |
| Underestimated effort (Category C: 3-4d → 8-11d) | ❌ Open | Re-estimate in TOOLING_SPEC |
| CLI name inconsistency ("ast" vs "ast-tools") | ❌ Open | Fix ADR-0011 line 125 |
| Version mismatch (v0.2.0 plan vs 0.1.0) | ❌ Open | Sync launch plan to 0.1.0 or bump pyproject.toml |
| Phase 7: 3/6 tasks already done | ✅ Planned | Recategorize as "Remaining Optimizations" |
| ADR-0009/0010: mark as Draft not implemented | ❌ Open | Add status badges to ADR frontmatter |

---

## 8. Reference

- `docs/specs/audits/forward-audit-comprehensive.md` — Full forward audit (2026-07-02)
- `docs/specs/audits/reverse-audit-comprehensive.md` — Full reverse audit (2026-07-02)
- `docs/specs/audits/adversarial-trust-v2.md` — Full adversarial audit (2026-07-14)
- `docs/specs/immutable-tool-cache-v3.md` — V3 tool cache spec (this workstream)
- `docs/specs/typed-trust-boundaries-v3.md` — V3 trust boundaries spec (this workstream)
- `docs/adrs/0009-reranker-integration.md` — Reranker ADR
- `docs/adrs/0010-architecture-governance-engine.md` — Governance ADR
- `docs/adrs/0011-pypi-name-decision-and-publishing-pipeline.md` — Publishing ADR
- `docs/adrs/0012-server-architecture-multi-mode.md` — Server architecture ADR