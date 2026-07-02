# Long-Term Plan — 4-16 Weeks (Phases 2-5)

> **Focus:** SDK, Knowledge Graph, Docker, Backup, Reporting, Dashboard, Agent Ecosystem, Multi-Machine, Monetization  
> **Timeline:** Phases 2-5, ~12 weeks total  
> **Prerequisites:** Phases 0-1 complete  

---

## Phase 2: SDK, Knowledge Graph, Docker (3 weeks)

### Prerequisites
- [x] Config directory (`~/.ast-tools/`) established
- [x] Data lifecycle commands operational (init, doctor, vacuum, curator)
- [x] Logging and audit infrastructure

### Deliverables
- [ ] Python SDK package (`ast-tools-sdk`)
- [ ] Knowledge graph query layer
- [ ] Docker image (`rapidwebs/ast-tools`)
- [ ] docker-compose.yml (server + optional dashboard)
- [ ] Systemd service file (`.service`)

### Key Decisions Needed
- SDK API surface: what's included vs MCP-only
- Knowledge graph: formal query API design
- Docker image: alpine vs slim, model bundling strategy

### Risk
- SDK API may change as MCP tools evolve — version pinning required
- Docker image with embedding model is ~1.5GB (model + dependencies) — CI build time may exceed 30min limits

---

## Phase 3: Backup, Reporting, Dashboard (3 weeks)

### Prerequisites
- [x] Python SDK published
- [x] Docker image available
- [x] Systemd service operational

### Deliverables
- [ ] Local backup/restore
- [ ] Remote backup (S3 backend)
- [ ] Incremental backup
- [ ] Encryption (AES-256-GCM)
- [ ] Text/CSV/JSON insights reporting (free tier)
- [ ] Markdown reporting (paid tier)
- [ ] Deduplication engine
- [ ] Uninstall command
- [ ] HTML dashboard (Tailwind + React + shadcn/ui) — local deployment

### Key Decisions Needed
- Backup retention policy (number of backups, age-based pruning)
- Dashboard tech stack confirmed (React vs vanilla, Tailwind CDN vs bundled)
- Report generation library (markdown→PDF: pandoc? weasyprint? wkhtmltopdf?)

### Risk
- HTML dashboard requires Node.js — adds build step complexity
- PDF generation is notoriously fragile — extensive testing needed

---

## Phase 4: Agent Ecosystem & Multi-Machine (3 weeks)

### Prerequisites
- [x] Backup/restore operational
- [x] Dashboard deployed
- [x] Uninstall command available

### Deliverables
- [ ] Gemini CLI extension
- [ ] Claude Code integration (CLAUDE.md + tuck)
- [ ] Multi-machine / distributed server support
- [ ] DOCX/PDF report generation (paid tier)
- [ ] Cross-repository symbol resolution
- [ ] Graph traversal API (BFS, DFS, shortest path)
- [ ] Usage analytics

### Key Decisions Needed
- Multi-machine architecture: SQLite shared via network FS vs separate DBs with merge
- Cross-repo resolution: how to match symbols across repos (by name? hash? canonical path?)
- Analytics: privacy-first (local-only) vs optional telemetry

### Risk
- Multi-machine is the highest-complexity feature in the roadmap — may need earlier prototyping
- Cross-repo resolution without an external symbol server is limited

### Dependency
- ADR-004 (Knowledge Graph Format) execution must be complete

---

## Phase 5: Monetization & Advanced Features (4 weeks)

### Prerequisites
- [x] Agent ecosystem operational
- [x] Multi-machine support available
- [x] Dashboard deployed

### Deliverables
- [ ] Tier gating system (free/team/pro/enterprise)
- [ ] License key system (offline-capable)
- [ ] SaaS deployment (multi-tenant dashboard)
- [ ] Subscription management (Stripe integration)
- [ ] Usage metering
- [ ] Concept extraction (high-level codebase understanding)
- [ ] Custom report builder
- [ ] VS Code extension
- [ ] Qwen Code extension
- [ ] Pro dashboard (advanced analytics, multi-machine admin)

### Key Decisions Needed
- Licensing model finalized: MIT core + paid extensions (ADR-003)
- SaaS pricing ($29/$49/custom)
- Stripe vs Paddle vs self-managed for payment processing

### Risk
- Concept extraction quality is hard to predict — may need AI model fine-tuning
- SaaS adds significant operational overhead (billing, auth, support)
- Licensing enforcement without telemetry is challenging

---

## Post-Launch (16+ Weeks)

### Potential Directions
- **ast-tools Hub:** A community registry of indexed open-source projects
- **AST-Tools Cloud:** Fully managed SaaS for enterprises
- **CI/CD Integration:** Native GitHub Actions, GitLab CI, Jenkins plugins
- **IDE Extension Marketplace:** VS Code, JetBrains, Vim/Neovim
- **Language Expansion:** Full support for 50+ languages via tree-sitter
- **Code Review Integration:** Auto-generated PR summaries based on impact analysis

---

## Gantt Overview

```
Phase 0 |▓▓▓▓▓▓▓▓▓▓▓▓▓▓|  
Phase 1 |       ▓▓▓▓▓▓▓▓▓▓▓▓▓▓|  
Phase 2 |              ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓|  
Phase 3 |                           ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓|  
Phase 4 |                                       ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓|  
Phase 5 |                                                    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓|
        └────Month 1────┴────Month 2────┴────Month 3────┴────Month 4────┘
```