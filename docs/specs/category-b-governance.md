# Phase B: Architecture Governance Engine — Specification

> **Version:** 1.0.0  
> **Status:** Draft  
> **Effort:** ~6 days  
> **Depends on:** Phase 7 (foundation), existing `module_imports`, `impact_analysis`, `dependency`  
> **Blocks:** Phase C3 (dashboard reads governance data)

---

## Problem

Large codebases accumulate architectural drift — modules import from layers they shouldn't, circular dependencies proliferate, and teams lack a machine-readable contract for what "good architecture" looks like.

## Solution

A declarative governance system that lets teams define **architectural rules in YAML**, then **scans the codebase** to verify compliance. Integrates with existing import graph infrastructure.

---

## Specification

### governance.yaml Format

```yaml
# Project root governance file
version: 1

# Layer definitions — ordered dependency direction
layers:
  - name: infrastructure
    description: "Database, external APIs, low-level utilities"
    tags: [db, cache, config]
  - name: domain
    description: "Business logic, domain models"
    tags: [model, service]
  - name: application
    description: "Use cases, application services"
    tags: [usecase, workflow]
  - name: presentation
    description: "CLI, API, UI"
    tags: [cli, api, web]

# Module → layer mapping (glob patterns)
mappings:
  - pattern: "**/database/**"
    layer: infrastructure
  - pattern: "**/domain/**"
    layer: domain
  - pattern: "**/usecase/**"
    layer: application
  - pattern: "**/cli/**"
    layer: presentation
  - pattern: "**/api/**"
    layer: presentation

# Layer dependency rules (optional — defaults to strict downward)
layer_rules:
  infrastructure:
    allowed_deps: []  # Can only import from itself
    forbidden_deps: [presentation]  # Explicit forbidden targets
  domain:
    allowed_deps: [infrastructure]
  application:
    allowed_deps: [infrastructure, domain]
  presentation:
    allowed_deps: [infrastructure, domain, application]

# Tag-based rules (optional overrides)
tag_rules:
  - from_tag: service
    allowed_import_tags: [model, db]
  - from_tag: cli
    allowed_import_tags: [service, usecase]

# Explicit allow/block overrides (file-level exceptions)
exceptions:
  - pattern: "**/legacy/**"
    reason: "Legacy module — migration in progress"
    severity: warn  # warn or error
```

### Scanner

Built on existing `_build_import_graph()` from `module_imports.py`:

1. Load `governance.yaml` (if exists, else generate default via `baseline`)
2. Walk each source file, determine its layer via glob mapping
3. For each import, check if target layer is in `allowed_deps`
4. Check tag-based rules if enabled
5. Produce violation report

### CLI Commands

```
ast governance init          — Create default governance.yaml (auto-detect layers)
ast governance check          — Run full scan, report violations
ast governance check --format json  — JSON output for CI
ast governance check --fail-on warn  — Exit non-zero on warnings too
ast governance diff           — Compare governance state vs baseline
ast governance report         — Generate HTML report with violation summary
ast governance baseline       — Snapshot current architecture as baseline
```

### Branch Diff

```
ast governance diff --base main  — Compare governance state between branches
```

Leverages `git diff --name-only` to find changed files, then re-scans only affected modules.

---

## Implementation Plan

### Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/ast_tools/governance/__init__.py` | Create | Module init |
| `src/ast_tools/governance/schema.py` | Create | governance.yaml loader + validator |
| `src/ast_tools/governance/scanner.py` | Create | Import graph + rule comparison engine |
| `src/ast_tools/governance/reporter.py` | Create | HTML/text report generation |
| `src/ast_tools/governance/differ.py` | Create | Branch comparison logic |
| `src/ast_tools/cli.py` | Modify | Add governance subcommands |
| `tests/governance/test_schema.py` | Create | Schema validation tests |
| `tests/governance/test_scanner.py` | Create | Scanner tests |
| `tests/governance/test_differ.py` | Create | Diff tests |
| `pyproject.toml` | Modify | Add `pyyaml` if not already |

### Dependencies

- `src/ast_tools/tools/module_imports.py:_build_import_graph()`
- `src/ast_tools/tools/dependency.py:build_import_graph()`
- `src/ast_tools/tools/impact_analysis.py` — for transitive impact
- `src/ast_tools/utils/file_utils.py:find_python_files()`

---

## Acceptance Criteria

- [ ] `ast governance init` creates valid `governance.yaml` from auto-detected layers
- [ ] `ast governance check` reports layer violations correctly
- [ ] Layer rules respect dependency direction (lower layers can't import upper)
- [ ] Tag rules work as subset filter
- [ ] Exceptions suppress violations with correct severity
- [ ] `ast governance diff --base main` detects branch-specific violations
- [ ] `governance.yaml` schema rejects invalid rules with clear error messages
- [ ] All existing 707+ tests still pass