# AST-Tools Documentation Scope Guidelines

**Version:** 1.0.0  
**Effective Date:** 2026-06-27  
**Purpose:** Ensure ast-tools documentation is suitable for public open-source release

---

## What Belongs in AST-Tools Documentation ✅

### Core API & Tool Documentation
- **Tool reference docs**: All 11+ MCP tools (`ast_grep`, `ast_edit`, `semantic_search`, etc.)
- **Interface contracts**: Input/output schemas, parameter descriptions
- **Usage examples**: Code snippets showing how to call each tool
- **Best practices**: Do's and don'ts for using ast-tools effectively

### Integration Guides
- **Hermes Agent integration**: Plugin setup, hook configuration, MCP server config
- **MCP server deployment**: Installation, configuration, verification steps
- **Third-party integrations**: sqlite-vec, tree-sitter, sentence-transformers

### Technical Specifications
- **Phase specs**: Technical specifications for major features (Phase 8, 9, 10A, etc.)
- **Architecture docs**: System design, component interactions, data flow
- **Schema documentation**: Database schema, migrations, versioning

### Public Workflows
- **Implementation plans**: Task breakdowns for public features
- **Audit reports**: Forward/reverse audits of public APIs
- **Completion reports**: Phase completion summaries with test results
- **Troubleshooting guides**: Common issues, error codes, solutions

### Research (General/Applicable)
- **Market analysis**: Competitive landscape, positioning (if relevant to users)
- **Technical research**: Embedding models, indexing strategies, performance benchmarks
- **Security patterns**: Validation approaches, attack mitigation

---

## What Does NOT Belong ❌

### Machine-Specific Configuration
- **Absolute paths**: `/home/sysop/Workspaces/`, `~/.hermes/` (use `$PROJECT_ROOT`, relative paths)
- **Machine identities**: `rw-workstation-01`, `rw-server-01`, hardware specs
- **Personal shell config**: User-specific environment setup, machine-specific deployment steps

### Personal Project References
- **Internal project names**: NexusAgent, FORGE, CATALYST, Antigravity, LocalBridge, GIDE (unless directly about ast-tools integration)
- **Personal workflows**: "Steven prefers", "sysop uses", user-specific patterns
- **Internal team references**: RapidWebs-specific processes, team member names (except in changelog/attribution)

### Hermes-Specific Config (Unless Public API)
- **Plugin implementation details**: Internal hook mechanics (document the _what_, not the _how_)
- **Config file paths**: `~/.hermes/config.yaml` → use "your Hermes config file"
- **Session-specific state**: `SESSION_STATE.md`, debugging notes, work-in-progress session logs

### Development Process Artifacts
- **Session state files**: `SESSION_STATE.md`, `PROJECT_STATE.md` (move to project journal)
- **Intermediate audit notes**: Draft audits, work-in-progress synthesis
- **Personal development logs**: Detailed refactoring journals (keep high-level lessons, remove personal notes)

---

## Path Conventions

### DO ✅
```markdown
- **Relative paths**: `src/ast_tools/tools/`, `docs/specs/`
- **Environment variables**: `$PROJECT_ROOT`, `$VIRTUAL_ENV`, `$HOME`
- **Generic references**: "your Hermes config", "the project root"
- **Cross-platform**: Use POSIX-style paths, avoid Windows-specific syntax
```

### DON'T ❌
```markdown
- **Absolute paths**: `/home/sysop/Workspaces/ast-tools/` → `$PROJECT_ROOT/`
- **User-specific**: `~/.hermes/` → "your Hermes profile directory"
- **Machine names**: `rw-workstation-01` → "your development machine"
- **Hardcoded credentials**: API keys, tokens, passwords (obviously)
```

---

## Examples: Good vs Bad Documentation

### Example 1: Installation Instructions

**❌ Bad:**
```markdown
## Step 1: Clone the Repository

```bash
cd /home/sysop/Workspaces/
git clone git@github.com:rapidwebs/ast-tools.git
cd /home/sysop/Workspaces/ast-tools
```

**Step 2: Configure Hermes**

Edit `~/.hermes/config.yaml` and add:
```yaml
mcp_servers:
  ast_tools:
    command: python3
    args:
      - /home/sysop/Workspaces/ast-tools/src/ast_tools_server.py
```
```

**✅ Good:**
```markdown
## Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/ast-tools.git
cd ast-tools
```

**Step 2: Configure Hermes**

Add the MCP server to your Hermes config file:
```yaml
mcp_servers:
  ast_tools:
    command: python3  # or `python` on Windows
    args:
      - path/to/ast-tools/src/ast_tools_server.py  # adjust path as needed
```
```

---

### Example 2: Plugin Documentation

**❌ Bad:**
```markdown
### ast-tools-context Plugin

Steven developed this plugin to inject context for NexusAgent workflows. 
Installed at `~/.hermes/plugins/ast-tools-context/` on rw-workstation-01.

The plugin uses pre_llm_call hooks that fire on queries about "ast_grep" or "structural".
```

**✅ Good:**
```markdown
### ast-tools-context Plugin

Automatically injects AST-Tools documentation when relevant queries are detected.

**Installation:**
```bash
cp -r hermes-plugins/ast-tools-context ~/.hermes/plugins/  # adjust path to your Hermes profile
```

**Behavior:**
Activates on queries mentioning: `ast`, `structural`, `code search`, `dependency analysis`, etc.

**Hooks:** `pre_llm_call`
```

---

### Example 3: Project References

**❌ Bad:**
```markdown
This tool was tested against the NexusAgent codebase at `/home/sysop/Workspaces/NexusAgent/`.
Steven uses this for the FORGE project's CATALYST module.

Performance benchmark: 2.3s on rw-server-01 (32-core, 128GB RAM).
```

**✅ Good:**
```markdown
This tool has been tested on large Python codebases (100K+ LOC).

**Performance benchmark:** ~2-3 seconds for 100K LOC on typical development hardware.

**Example use cases:**
- Multi-package Python applications
- Microservice architectures with shared libraries
- Frameworks with deep inheritance hierarchies
```

---

## Documentation Organization

### Root Level (`/docs/`)
- `DOCUMENTATION_INDEX.md` — Navigation guide
- `TROUBLESHOOTING.md` — Common issues & solutions
- `CONTRIBUTING.md` — This file + contribution guidelines

### Specifications (`/docs/specs/`)
- `phase*-spec.md` — Technical specifications for each phase
- `semantic-db-phase*-v*.md` — Semantic database specs
- `refactor-modular-v1.md` — Architecture specs

### Plans (`/docs/plans/`)
- `phase*-implementation-plan.md` — Implementation task breakdowns
- `semantic-db-phase*-v*.md` — Implementation plans

### Audits (`/docs/audits/`)
- `phase*-forward-audit.md` — Forward audits
- `phase*-reverse-audit.md` — Reverse audits
- `phase*-synthesis.md` — Audit synthesis reports

### Reports (`/docs/reports/`)
- `PHASE*_COMPLETE.md` — Phase completion reports
- `PHASE*_SYNTHESIS.md` — Phase synthesis
- `documentation-audit-report-YYYY-MM-DD.md` — Documentation audits

### Research (`/docs/research/`)
- `market-analysis*.md` — Market research, competitive analysis
- `embedding-*.md` — Embedding model research
- `semantic-database-research.md` — Technical research

### Archive (`/docs/archive/`)
- Personal/development artifacts
- Superseded documentation
- Session-specific notes

---

## Remediation Workflow

When auditing existing documentation:

1. **Classify each file:**
   - ✅ **Core** (90%+ ast-tools): Edit to remove personal refs
   - ⚠️ **Mixed** (50-90% ast-tools): Extract ast-tools content, archive rest
   - ❌ **Off-topic** (<50% ast-tools): Move to archive or external repo

2. **Fix common issues:**
   - Replace absolute paths with relative/env vars
   - Remove machine names, user names, personal preferences
   - Generalize project-specific examples
   - Move session state to archive

3. **Commit in stages:**
   - Stage 1: Move off-topic files to archive
   - Stage 2: Edit mixed files (extract/move)
   - Stage 3: Polish core docs (path cleanup, generalization)
   - Stage 4: Create this guideline + audit report

---

## Approval Checklist for Open-Source Release

Before publishing:

- [ ] No absolute paths containing `/home/sysop/` or machine names
- [ ] No references to internal projects (NexusAgent, FORGE, etc.) unless clearly marked as integration examples
- [ ] No user-specific preferences ("Steven prefers", "sysop uses")
- [ ] All examples use relative paths or environment variables
- [ ] Session state files moved to archive
- [ ] Plugin docs describe behavior, not implementation internals
- [ ] Market analysis focuses on public competitive landscape
- [ ] All code snippets are generic/representative, not project-specific
- [ ] Changelog attributes are professional (no internal team politics)
- [ ] README.md is clean, professional, installation-ready

---

## Questions?

If unsure whether content belongs:
1. **Ask:** "Would this be useful to a stranger installing ast-tools from GitHub?"
2. **If no:** Move to archive or personal notes
3. **If maybe:** Flag for community review, keep but mark as "developing"

---

**Maintainers:** Update this guideline when new documentation patterns emerge.
**Review cycle:** Quarterly, or before major releases.