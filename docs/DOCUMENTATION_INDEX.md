# AST-Tools Documentation Index

**Last updated:** 2026-08-01  
**Version:** 0.1.0

---

## Quick Start

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Project overview & 43 tools |
| [SETUP_INSTRUCTIONS.md](../SETUP_INSTRUCTIONS.md) | Hermes plugin installation |
| [AST_TOOLS_QUICKSTART.md](AST_TOOLS_QUICKSTART.md) | User guide & workflows |

---

## Active Documentation

### User Guides
| Document | Purpose |
|----------|---------|
| [CLI_REFERENCE.md](CLI_REFERENCE.md) | Complete CLI reference (11 commands) |
| [ENHANCED_DEAD_CODE.md](ENHANCED_DEAD_CODE.md) | Dead code detection with 6 FP reductions |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues & fixes |
| [USAGE_RULES.md](USAGE_RULES.md) | "Don't modify AST-Tools" rules |

### Reference
| Document | Purpose |
|----------|---------|
| [SCOPE.md](SCOPE.md) | Documentation scope guidelines |
| [MARKET_ANALYSIS_2026.md](MARKET_ANALYSIS_2026.md) | Market research & competitive landscape |
| [COMPETITIVE_FEATURE_PARITY_20260628.md](COMPETITIVE_FEATURE_PARITY_20260628.md) | Competitive analysis (historical snapshot) |

---

## Historical Archives

### Consolidated History
| Document | Content |
|----------|---------|
| [AUDITS_HISTORY.md](AUDITS_HISTORY.md) | All audit reports (phases 0-9) |
| [SPECS_HISTORY.md](SPECS_HISTORY.md) | All specifications |
| [PLANS_HISTORY.md](PLANS_HISTORY.md) | All implementation plans |
| [REPORTS_HISTORY.md](REPORTS_HISTORY.md) | All reports |

### Archived Documents
See [archive/](archive/) for obsolete docs (21 files):
- Phase summaries, session states, old specs
- Superseded audits and plans
- Research notes from early development

---

## Project Stats

| Metric | Value |
|--------|-------|
| **Active docs** | 12 |
| **Archived docs** | 21 |
| **Consolidated history docs** | 4 |
| **Total markdown files** | 37+ |
| **MCP Tools** | 43 |
| **CLI Commands** | 11 |
| **Test Files** | 33 |
| **Source Files** | 69 |
| **Lines of Code** | 17,581 |
| **Tests collected** | 461+ |

---

## Key Workflows

### Structural Analysis
```bash
# Search codebase
ast search "authentication logic" --limit 10

# Navigate to symbol
ast navigate "UserController"

# Impact analysis
ast blast-radius src/auth.py:42

# Find dead code
ast find-dead --format json
```

### Semantic Search (Python API)
```python
from ast_tools.tools.semantic_search import _tool_semantic_search
result = await _tool_semantic_search({
    "query": "websocket auth",
    "k": 10,
    "inject_context": True,
    "token_budget": 4096
})
```

---

## See Also

- [CHANGELOG.md](../CHANGELOG.md) — Version history
- [pyproject.toml](../pyproject.toml) — Project configuration
- [tests/](../tests/) — Test suite (33 files)