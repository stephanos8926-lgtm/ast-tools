# Risk Register — AST-Tools Ecosystem Implementation

> **Date:** 2026-07-31  
> **Author:** Lucien  
> **Status:** Living document — updated as risks are identified or retired  

---

## Risk Scoring

| Score | Likelihood × Impact | Response |
|-------|---------------------|----------|
| 🔴 Critical | High × High | Must mitigate before proceeding |
| 🟠 High | Medium × High or High × Medium | Active mitigation required |
| 🟡 Medium | Low × High or Medium × Medium | Monitor, plan response |
| 🔵 Low | Low × Medium or Low × Low | Accept or defer |

---

## Phase 0 Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation |
|----|------|-----------|--------|-------|------------|
| R0-01 | Config migration from `~/.cache/ast-tools/` breaks existing deployments | Medium | High | 🟠 High | Fallback: if `~/.ast-tools/` doesn't exist but `~/.cache/ast-tools/` does, migrate on first run. Document manual migration steps. |
| R0-02 | Plugin backwards compatibility breaks during tokens.yaml transition | Medium | High | 🟠 High | Ship both codepaths during transition: try tokens.yaml first, fall back to hardcoded defaults. Remove hardcoded path in Phase 2. |
| R0-03 | SKILL.md files become stale after tools are updated | High | Low | 🟡 Medium | Add SKILL.md generation to CI pipeline — auto-regenerate when tool schemas change. |

---

## Phase 1 Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation |
|----|------|-----------|--------|-------|------------|
| R1-01 | Model download fails during setup wizard | Medium | High | 🟠 High | Add resume support (download to tmp, verify checksum). Offer `--skip-model` flag for offline environments. |
| R1-02 | Curator daemon conflicts with concurrent index operations | Medium | Medium | 🟡 Medium | Use SQLite WAL mode with retry logic. Curator acquires a write lock; other operations wait with timeout. |
| R1-03 | Doctor command has false negatives (reports health but system broken) | Low | High | 🟡 Medium | Exhaustive check list: db integrity, model responds, index returns results, config valid, dependencies available. |
| R1-04 | PII redaction produces false positives (flags legitimate code) | Medium | Medium | 🟡 Medium | Default to "flag for review" rather than "auto-redact". Configurable allowlist. |

---

## Phase 2 Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation |
|----|------|-----------|--------|-------|------------|
| R2-01 | SDK API changes as MCP tools evolve — breaks consumers | High | Medium | 🟡 Medium | Version SDK in lockstep with MCP tools. Semantic versioning: breaking changes = major version bump. |
| R2-02 | Docker image exceeds CI build time limits (model = ~1.5GB) | High | High | 🟠 High | Multi-stage build: base image without model, model downloaded at runtime. Or use GitHub Actions with larger runners. |
| R2-03 | Knowledge graph queries are too slow on large codebases (>100K symbols) | Medium | High | 🟠 High | Benchmark with 100K symbol dataset. Optimize with indexes. Consider paginated query results. Document performance envelope. |

---

## Phase 3 Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation |
|----|------|-----------|--------|-------|------------|
| R3-01 | Backup takes too long for large databases (>1GB) | Medium | Medium | 🟡 Medium | Default to database-only backup (skip models). Offer incremental mode. Show progress bar during backup. |
| R3-02 | PDF report generation is fragile across platforms | High | Medium | 🟡 Medium | Pin PDF generation tool version. Test across Linux/macOS/Windows. Use simple HTML→PDF (weasyprint) rather than complex layouts. |
| R3-03 | Encryption key management confuses users | Medium | Low | 🔵 Low | Clear CLI prompts with password strength meter. Document key recovery: "No password = no data. There is no backdoor." |

---

## Phase 4 Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation |
|----|------|-----------|--------|-------|------------|
| R4-01 | Multi-machine support introduces consistency issues | High | High | 🔴 Critical | Start with shared-database model (NFS-backed SQLite). Document limitations. Only add distributed model if demand justifies. |
| R4-02 | Cross-repo symbol matching is unreliable | High | Medium | 🟠 High | Start with exact-match (symbol name + file path). Add fuzzy matching as optional enhancement. Document accuracy guarantees. |

---

## Phase 5 Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation |
|----|------|-----------|--------|-------|------------|
| R5-01 | Licensing enforcement without telemetry is challenging | Medium | High | 🟠 High | Use offline license file validation (signed JWT). Periodic manual verification prompts. Accept that determined users can bypass — focus on honest users. |
| R5-02 | SaaS adds significant operational overhead | High | Medium | 🟠 High | Start with self-hosted only. SaaS only if demand justifies dedicated ops. Use existing infrastructure (Railway, Render, Fly.io) for MVP. |
| R5-03 | Concept extraction quality disappoints users | Medium | High | 🟠 High | Set expectations: "Experimental — accuracy may vary." Make it a configurable feature, not the headline deliverable. |

---

## Cross-Phase Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation |
|----|------|-----------|--------|-------|------------|
| R0-01 | Feature creep — roadmap scope exceeds capacity | High | High | 🔴 Critical | Strict phase scoping. Each phase has a hard scope boundary. Features not in current phase go to "Icebox" backlog. Monthly reprioritization. |
| R0-02 | Single developer bottleneck (Lucien only) | High | High | 🔴 Critical | Prioritize self-documenting code and comprehensive CI. Write contribution guide (CONTRIBUTING.md) early. Build for handoff-readiness. |
| R0-03 | Test suite becomes brittle at >500 tests | Medium | Medium | 🟡 Medium | Invest in test infrastructure: conftest fixtures, test factories, flaky test detection, test tagging. |
| R0-04 | 4GB workstation RAM limits development velocity | High | Medium | 🟠 High | Offload heavy builds/tests to server (rapidwebs). Use targeted test runs instead of full suite. Consider GitHub Codespaces for model-dependent work. |

---

## Retired Risks

| ID | Risk | Retired | Reason |
|----|------|---------|--------|
| — | — | — | — |