# AST-Tools Documentation Index

**Last updated:** 2026-06-29  
**Version:** 0.1.0

---

## Quick Start

| Document | Purpose |
|----------|---------|
| [README.md](../README.md) | Project overview |
| [SETUP_INSTRUCTIONS.md](../SETUP_INSTRUCTIONS.md) | Installation & setup |
| [AST_TOOLS_QUICKSTART.md](AST_TOOLS_QUICKSTART.md) | User guide & workflows |

---

## Active Documentation

### User Guides
| Document | Purpose |
|----------|---------|
| [CLI_REFERENCE.md](CLI_REFERENCE.md) | Complete CLI reference (11 commands) |
| [ENHANCED_DEAD_CODE.md](ENHANCED_DEAD_CODE.md) | Dead code detection guide |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues & fixes |
| [USAGE_RULES.md](USAGE_RULES.md) | "Don't modify AST-Tools" rules |

### Reference
| Document | Purpose |
|----------|---------|
| [SCOPE.md](SCOPE.md) | Project scope & boundaries |
| [MARKET_ANALYSIS_2026.md](MARKET_ANALYSIS_2026.md) | Market research |
| [COMPETITIVE_FEATURE_PARITY_20260628.md](COMPETITIVE_FEATURE_PARITY_20260628.md) | Competitive analysis |

---

## Historical Archives

### Consolidated History
| Document | Content |
|----------|---------|
| [AUDITS_HISTORY.md](AUDITS_HISTORY.md) | All audit reports (phase 1-9) |
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
| **Consolidated docs** | 4 |
| **Total markdown files** | 37 |
| **MCP Tools** | 42 |
| **CLI Commands** | 11 |
| **Test Files** | 31 |
| **Lines of Code** | 24,609 |

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

### TypeScript/TSX
```bash
# Use MCP tool directly
hermes mcp call ast-tools ts_edit '{
  "file": "src/component.tsx",
  "operation": "rename_identifier",
  "params": {"old_name": "Old", "new_name": "New"},
  "lang": "tsx"
}'
```

### Semantic Search (Python API)
```python
from ast_tools.tools.semantic_search import hybrid_search
results = hybrid_search("websocket auth", k=10)
```

---

## See Also

- [CHANGELOG.md](../CHANGELOG.md) - Version history
- [pyproject.toml](../pyproject.toml) - Project configuration
- [tests/](../tests/) - Test suite (31 files)
