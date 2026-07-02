# AST-Tools Ecosystem — Comprehensive Roadmap

> **Version:** 1.0.0  
> **Author:** Lucien (Lead Digital Architect, RapidWebs Enterprise)  
> **Date:** 2026-07-31  
> **Status:** Draft — Pending ADRs, Phase Audits, and Final Sign-off  
> **License:** MIT  

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Vision Statement](#vision-statement)
3. [Core Architecture Principles](#core-architecture-principles)
4. [Project Inventory — Current State](#project-inventory--current-state)
5. [Full Feature Taxonomy](#full-feature-taxonomy)
6. [Monetization & Distribution Model](#monetization--distribution-model)
7. [Implementation Phases Overview](#implementation-phases-overview)
8. [ADR Index](#adr-index)
9. [Planning Documents](#planning-documents)

---

## Executive Summary

AST-Tools is a structural code analysis and editing platform built on the Model Context Protocol (MCP). It provides 43+ tools for semantic code search, AST-based refactoring, dependency analysis, impact assessment, and index management. Currently at v0.1.0 (Beta), the project has a working MCP server, 17+ CLI tools, 3 Hermes plugins, a SQLite+vector database backend, and a CI/CD pipeline with GitHub Actions publishing to PyPI.

**The gap:** The project exists as a powerful MCP server but lacks the infrastructure, ecosystem, and productization layers needed for production-grade adoption, monetization, and multi-platform agent integration. This roadmap defines the complete path from "functional MCP server" to "self-sustaining code intelligence platform."

**Target state:** A fully self-contained code intelligence ecosystem with:
- Multi-platform agent integration (Hermes, Gemini CLI, Claude Code, Qwen Code)
- Web dashboard for configuration, insights, and administration
- Tiered SaaS/self-hosted monetization
- Data lifecycle management (init → doctor → curator → vacuum → backup/restore → uninstall)
- Knowledge graph support
- SDK for programmatic consumption
- Multi-machine distributed deployment support

---

## Vision Statement

AST-Tools will become the **universal code intelligence layer** — an open-source, agent-agnostic platform that any AI agent (Hermes, Claude Code, Gemini CLI, Qwen Code, etc.) can plug into for deep structural understanding of any codebase.

**Core identity:** We are an infrastructure layer, not an application. Our job is to parse, index, analyze, and serve code intelligence to any consumer that speaks our protocol.

**Why this matters:** Every coding agent needs to understand code structure. Currently, every agent builds its own partial solution (Claude Code has grep+regex, Gemini CLI has its own index, Codex has a different one). AST-Tools provides a standardized, open-source, and comprehensive solution that any agent can adopt.

**The 10-year ambition:** A codebase knowledge graph that spans millions of open-source repositories — a "Google for code structure" that agents query instead of rebuilding indexes from scratch.

---

## Core Architecture Principles

1. **Agent-Agnostic Protocol:** All functionality exposed via MCP. No Hermes-specific dependencies in core. The Hermes plugins, SKILL.md files, and CLI extensions are adapters that wrap the MCP protocol.

2. **Data Lifecycle First:** Every piece of data must have an init → maintain → curator → vacuum → backup → cleanup → uninstall lifecycle. No orphaned data, no stale indexes, no unbounded database growth.

3. **Layered Monetization:** Free tier (CLI + MCP + raw stats) → Paid tier (formatted reports, PDF, docs) → Pro tier (dashboard, multi-machine, advanced analytics). Never degrade the free tier; always add value on top.

4. **Self-Healing Infrastructure:** Doctor command diagnoses and fixes common issues. Curator daemon prunes stale data. Vacuum reclaims space. Backup/restore provides safety nets. The system should survive machine failures gracefully.

5. **Privacy by Default:** PII redaction during curation, optional encryption for backups, no telemetry without opt-in. On-premise first, SaaS optional.

6. **Distributed by Design:** The index format and query protocol must support multi-machine deployments from day one. A single SQLite database scales to ~1M symbols; beyond that, the architecture should support sharding and federation.

---

## Project Inventory — Current State

### What Exists (v0.1.0)

| Component | Status | Detail |
|-----------|--------|--------|
| **MCP Server** | ✅ Complete (43 tools) | 17 core + 26 utility/analysis/index tools |
| **CLI** | ✅ Complete | `ast-tools-server`, `ast-tools-project`, `ast-tools` entry points |
| **Hermes Plugins** | ✅ 3 shipped | ast-tools-context, ast-tools-tokens, ast-tools-codebase-index |
| **SQLite Database** | ✅ Schema v5 | Symbols, embeddings, edges, dependency metrics, audit_log |
| **FTS5 Search** | ✅ <10ms | Full-text search over indexed symbols |
| **Vector Search** | ✅ <50ms | sqlite-vec with sentence-transformers (bge-small-en-v1.5) |
| **6-Factor RRF Fusion** | ✅ <100ms hybrid | Semantic (40%) + recency (15%) + usage (15%) + kind (10%) + proximity (10%) + callgraph (10%) |
| **CI/CD Pipeline** | ✅ GitHub Actions | Lint → test (matrix 3.10-3.13) → build → publish PyPI |
| **Pre-commit hooks** | ✅ Configured | `.pre-commit-config.yaml` with ruff |
| **Tests** | ✅ 461+ tests | Pytest suite with coverage across 33+ files |
| **Build** | ✅ Wheel + sdist | Hatchling build, published to PyPI |
| **Docs** | ⚠️ Partial | Quickstart, CLI reference, usage rules, troubleshooting exist; user-facing docs incomplete |
| **Knowledge Graph** | ⚠️ Foundation | `knn_builder.py` exists, KNN graph built from embeddings, but no formal KG query layer |
| **Curator** | ⚠️ Partial | `curator/daemon.py` exists but not production-ready |
| **File Watcher** | ⚠️ Partial | `watcher/daemon.py` exists, watchdog-based, reindex dispatch stubbed |

### What's Missing (Full Gap Analysis)

#### Infrastructure & Data Lifecycle
- [ ] `~/.ast-tools/` config directory with `config/tokens.yaml`
- [ ] First-time setup wizard (db init, model download, index creation)
- [ ] Doctor command (healthcheck: db integrity, model loaded, index consistent)
- [ ] Maintenance commands (vacuum, curation, pruning, dedup, cleanup)
- [ ] Shutdown/uninstall logic (cleanup config, db, caches)
- [ ] Data backup/restore (local + remote, incremental, optional encryption)
- [ ] PII redaction during curator runs
- [ ] Logging with rotation

#### Agent Ecosystem
- [ ] Bundled SKILL.md files (cross-platform: Hermes, Claude Code, Gemini CLI, Qwen Code, etc.)
- [ ] Official Hermes plugins (3 shipped, need maintenance + 1 more: project-context)
- [ ] Gemini CLI extension
- [ ] Claude Code extension
- [ ] Qwen Code extension
- [ ] VS Code extension (MCP-based)

#### SDK & API
- [ ] Python SDK (programmatic consumption of code intelligence)
- [ ] TypeScript SDK (for web dashboard and Node.js consumers)
- [ ] REST API (optional HTTP gateway alongside MCP)

#### Knowledge Graph
- [ ] Formal knowledge graph query layer (beyond KNN)
- [ ] Cross-repository symbol resolution
- [ ] Graph traversal API (neighbors, paths, clusters)
- [ ] Concept extraction (what does this codebase "do"?)

#### Deployment & Operations
- [ ] Docker image
- [ ] docker-compose.yml (server + dashboard)
- [ ] Systemd service file
- [ ] Multi-machine / distributed server support
- [ ] Healthcheck endpoint

#### Monetization & Productization
- [ ] Tiered feature gating
- [ ] Report generation (markdown → docx → PDF → HTML)
- [ ] Web dashboard (Tailwind + React + shadcn/ui)
- [ ] SaaS deployment option
- [ ] License key / subscription management

---

## Full Feature Taxonomy

### Core Infrastructure (Foundation Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| CORE-01 | Config directory (`~/.ast-tools/`) | P0 | 0 | Standardized config file structure |
| CORE-02 | tokens.yaml | P0 | 0 | Token budget, context length, threshold config |
| CORE-03 | Logging framework | P0 | 0 | Structured logging with rotation |
| CORE-04 | Error handling standardization | P0 | 0 | Consistent error codes across all tools |

### Data Lifecycle (Operations Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| DATA-01 | Setup wizard | P0 | 1 | Interactive first-time setup (db init, model download, index creation) |
| DATA-02 | Doctor command | P0 | 1 | Healthcheck: db integrity, model loaded, index consistent, dependencies |
| DATA-03 | Vacuum | P1 | 1 | SQLite vacuum + reindex, space reclamation |
| DATA-04 | Curation daemon | P1 | 1 | Stale data pruning, orphaned symbol cleanup, dedup |
| DATA-05 | Cleanup command | P1 | 1 | Remove temporary files, stale indexes, expired caches |
| DATA-06 | Deduplication engine | P2 | 3 | Content-hash based dedup with confidence scoring |
| DATA-07 | Uninstall logic | P0 | 3 | Clean removal of all artifacts (config, db, caches, logs) |

### SDK & API (Consumption Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| SDK-01 | Python SDK | P1 | 2 | Programmatic consumption of code intelligence |
| SDK-02 | REST API gateway | P2 | 3 | HTTP gateway alongside MCP |
| SDK-03 | TypeScript SDK | P2 | 4 | For web dashboard and Node.js consumers |

### Knowledge Graph (Intelligence Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| KG-01 | Knowledge graph query layer | P1 | 2 | Formal KG queries beyond KNN (neighbors, paths, clusters) |
| KG-02 | Cross-repo symbol resolution | P2 | 4 | Resolve symbols across repository boundaries |
| KG-03 | Graph traversal API | P2 | 4 | Breadth-first, depth-first, shortest path traversals |
| KG-04 | Concept extraction | P2 | 5 | High-level understanding of codebase purpose |

### Agent Ecosystem (Integration Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| AGENT-01 | SKILL.md cross-platform bundle | P0 | 0 | Platform-agnostic skill files for Hermes, Claude Code, etc. |
| AGENT-02 | Hermes plugin maintenance | P1 | 1 | Update plugins: config-driven tokens.yaml, project-context |
| AGENT-03 | Gemini CLI extension | P2 | 4 | Gemini CLI adapter for ast-tools tools |
| AGENT-04 | Claude Code extension | P2 | 4 | Claude Code adapter |
| AGENT-05 | Qwen Code extension | P3 | 5 | Qwen Code adapter |
| AGENT-06 | VS Code extension | P3 | 5 | MCP-based VS Code extension |

### Deployment & Operations (Infrastructure Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| OPS-01 | Docker image | P1 | 2 | Production Docker image |
| OPS-02 | docker-compose.yml | P1 | 2 | Server + optional dashboard compose |
| OPS-03 | Systemd service | P1 | 2 | Service file for persistent operation |
| OPS-04 | Multi-machine support | P2 | 4 | Distributed server deployment |
| OPS-05 | Healthcheck endpoint | P1 | 2 | MCP healthcheck for orchestration |

### Backup & Disaster Recovery (Safety Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| BACKUP-01 | Local backup | P1 | 3 | Archive + compress indexes and config |
| BACKUP-02 | Remote backup | P2 | 3 | S3/SFTP/rsync remote backup |
| BACKUP-03 | Incremental backup | P2 | 3 | Only changed data since last backup |
| BACKUP-04 | Encryption | P2 | 3 | Optional GPG/AES encryption for backups |
| BACKUP-05 | Restore command | P1 | 3 | Full + selective restore from backup |

### Reporting & Insights (Value Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| REPORT-01 | Text/CSV/JSON stats | P1 | 2 | Raw codebase insights (free tier) |
| REPORT-02 | Markdown reports | P2 | 3 | Human-readable markdown insight reports (paid) |
| REPORT-03 | DOCX reports | P3 | 4 | Word document format (paid) |
| REPORT-04 | PDF reports | P3 | 4 | PDF generation (paid) |
| REPORT-05 | HTML dashboard | P2 | 3 | Tailwind + React + shadcn/ui dashboard (pro) |
| REPORT-06 | Custom report builder | P3 | 5 | User-configurable report content and layout |

### Privacy & Security (Trust Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| SEC-01 | PII redaction in curator | P1 | 1 | Redact emails, keys, passwords from db during curator runs |
| SEC-02 | Backup encryption | P2 | 3 | AES-256-GCM encryption for backup artifacts |
| SEC-03 | Audit logging | P1 | 0 | Structured audit log for all destructive operations |
| SEC-04 | Configuration validation | P1 | 0 | Schema validation for all config files |

### Dashboard & Administration (Management Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| DASH-01 | Web dashboard (local) | P2 | 3 | Local web UI for configuration, insights, administration |
| DASH-02 | SaaS deployment | P3 | 5 | Cloud-hosted dashboard with multi-tenant support |
| DASH-03 | Usage analytics | P2 | 4 | Index health, query frequency, storage trends |

### Monetization Infrastructure (Revenue Layer)

| ID | Feature | Priority | Phase | Description |
|----|---------|----------|-------|-------------|
| MON-01 | Tier gating | P3 | 4 | Feature access control by tier |
| MON-02 | License key system | P3 | 4 | Offline license validation |
| MON-03 | Subscription management | P3 | 5 | Stripe integration for SaaS |
| MON-04 | Usage metering | P3 | 5 | API call tracking for metered billing |

---

## Monetization & Distribution Model

### Tier Structure

| Tier | Price (est.) | Access | Features |
|------|-------------|--------|----------|
| **Free** | $0 | MCP server, CLI, all core tools | Raw stats (text/CSV/JSON), single machine, community support |
| **Team** | $29/mo | Everything free + | Markdown reports, docx/pdf export, backup/restore, email support |
| **Pro** | $49/mo | Everything team + | Web dashboard, advanced analytics, multi-machine, dedicated support |
| **Enterprise** | Custom | Everything pro + | SaaS deployment, SSO, SLA, on-premise license, custom integrations |

### Distribution Channels

| Channel | Tier | Purpose |
|---------|------|---------|
| PyPI | Free | pip install ast-tools |
| Docker Hub | Free/Team | docker pull rapidwebs/ast-tools |
| GitHub Releases | Free | Source + pre-built wheels |
| npm | Free | @rapidwebs/ast-tools-sdk (TypeScript) |
| SaaS Portal | Pro/Enterprise | Managed dashboard + API |

---

## Implementation Phases Overview

| Phase | Name | Focus | Effort (est.) | Dependencies |
|-------|------|-------|---------------|-------------|
| **0** | Foundation & Configuration | Config directory, tokens.yaml, logging, audit log, SKILL.md bundle | 1 week | None |
| **1** | Data Lifecycle & Operations | Setup wizard, doctor, vacuum, curator, PII redaction | 2 weeks | Phase 0 |
| **2** | SDK, Knowledge Graph, Docker | Python SDK, KG query layer, Docker image, systemd | 3 weeks | Phase 1 |
| **3** | Backup, Reporting, Dashboard | Backup/restore, insights, HTML dashboard, uninstall | 3 weeks | Phase 2 |
| **4** | Agent Ecosystem & Multi-Machine | Gemini/Claude Code extensions, distributed support, analytics | 3 weeks | Phase 3 |
| **5** | Monetization & Advanced Features | Tier gating, SaaS, pro dashboard, concept extraction | 4 weeks | Phase 4 |

**Total estimated: 16 weeks (4 months)**

See `docs/roadmap/phases/` for detailed phase implementation plans.

---

## ADR Index

Key Architecture Decision Records are at `docs/roadmap/adrs/`:

| ADR | Title | Status |
|-----|-------|--------|
| ADR-001 | Config Directory Structure | Draft |
| ADR-002 | Data Lifecycle Architecture | Draft |
| ADR-003 | Monetization vs Open Source Boundary | Draft |
| ADR-004 | Knowledge Graph Storage Format | Draft |
| ADR-005 | Multi-Platform Agent Strategy | Draft |
| ADR-006 | Backup & Encryption Architecture | Draft |

---

## Planning Documents

Located at `docs/roadmap/planning/`:

| Document | Purpose |
|----------|---------|
| SHORT_TERM.md | Next 4 weeks — Phases 0-1 |
| LONG_TERM.md | 4-16 week outlook — Phases 2-5 |
| RISK_REGISTER.md | Identified risks and mitigation strategies |
| DEPENDENCY_MAP.md | Cross-phase dependency graph |
| MILESTONE_TIMELINE.md | Gantt-style timeline view |

---

*This roadmap is a living document. Phase details evolve as audits complete and user feedback is incorporated.*