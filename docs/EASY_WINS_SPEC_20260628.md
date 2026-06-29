# Easy Wins Specification — CLI Tool + Dead Code Detection

**Date:** 2026-06-28  
**Mode:** MEDIUM (plan-and-audit workflow)  
**Author:** Lucien (RapidWebs Enterprise)  
**Status:** DRAFT — Pending Audits

---

## Overview

Two high-impact, low-effort features to improve ast-tools adoption and daily UX:

1. **CLI Tool** — Standalone command-line interface for humans (not just MCP for agents)
2. **Dead Code Detection** — Find unreferenced functions, classes, methods

**Why these first:**
- CLI tool: Improves demoability, testing, human workflow (10h effort)
- Dead code: Addresses competitive gap vs nervx/GitNexus (15h effort)
- Both are **independent** (can be implemented in parallel)
- Neither requires knowledge graph completion (Phase 10's 60h effort)

---

## Feature 1: CLI Tool (`ast-tools` command)

### Goals

1. Enable humans to use ast-tools WITHOUT an agent
2. Improve demoability (conference talks, tutorials, testing)
3. Provide human-readable output formats (markdown, JSON, tree)
4. Complement MCP server (not replace it)

### Interface Design

**Command structure:**
```bash
ast-tools <command> [options]

Commands:
  search <query>              # Search codebase (hybrid: FTS5 + vectors)
  nav <symbol>                # Navigate to symbol definition
  blast-radius <symbol>       # Impact analysis (callers + callees)
  callers <symbol>            # Who calls this symbol?
  callees <symbol>            # What does this symbol call?
  index-status                # Show index stats (files, symbols, embeddings)
  refresh                     # Manual index refresh
```

**Output formats:**
```bash
ast-tools search "auth" --format=markdown   # Default: formatted markdown
ast-tools search "auth" --format=json       # Machine-readable
ast-tools search "auth" --format=tree       # Tree-style (like tree command)
ast-tools search "auth" --format=compact    # File:line only (for scripts)
```

**Common options:**
```bash
--path <dir>            # Project path (default: current dir)
--lang <python|js|ts>   # Language filter
--kind <function|class> # Symbol kind filter
--limit <N>             # Max results (default: 10)
--format <fmt>          # Output format
--no-context            # Skip code snippets (faster)
```

### Example Workflows

**Developer exploring unfamiliar codebase:**
```bash
$ cd ~/Workspaces/myproject
$ ast-tools search "user authentication" --format=markdown
```

**Engineer checking blast radius before refactor:**
```bash
$ ast-tools blast-radius SessionManager.validate_token
# Returns: 12 direct callers, 3 transitive dependents, risk score: HIGH
```

**Scripting automation:**
```bash
$ ast-tools callers deprecated_function --format=compact > refactor_todo.txt
```

### Technical Design

**Entry point:**
```python
# src/ast_tools/cli.py
import argparse
from ast_tools.database.connection import get_db_path
from ast_tools.tools.semantic_search import hybrid_search_with_context
from ast_tools.tools.find_references import find_references
from ast_tools.tools.impact_analysis import impact_analysis

def main():
    parser = argparse.ArgumentParser(prog='ast-tools')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # search command
    search_parser = subparsers.add_parser('search', help='Search codebase')
    search_parser.add_argument('query')
    search_parser.add_argument('--path', default='.')
    search_parser.add_argument('--format', choices=['markdown', 'json', 'tree', 'compact'], default='markdown')
    search_parser.add_argument('--limit', type=int, default=10)
    # ... more args
    
    args = parser.parse_args()
    
    if args.command == 'search':
        run_search(args)
    elif args.command == 'blast-radius':
        run_blast_radius(args)
    # ... more commands

if __name__ == '__main__':
    main()
```

**Formatters:**
```python
# src/ast_tools/cli/formatters.py

def format_as_markdown(results):
    """Human-readable markdown with code snippets."""
    lines = []
    for symbol in results:
        lines.append(f"### `{symbol['qualified_name']}`")
        lines.append(f"**File:** `{symbol['file']}`:{symbol['line']}\n")
        lines.append(f"_{symbol['docstring']}_\n")
        lines.append("```python")
        lines.append(symbol['source_snippet'])
        lines.append("```\n")
    return '\n'.join(lines)

def format_as_compact(results):
    """File:line only — for scripting."""
    return [f"{r['file']}:{r['line']}" for r in results]
```

**pyproject.toml entry point:**
```toml
[project.scripts]
ast-tools = "ast_tools.cli:main"
```

### Test Plan

```python
# tests/test_cli.py

def test_cli_search_markdown():
    """CLI search returns markdown format."""
    result = runner.invoke(app, ['search', 'auth', '--format=markdown'])
    assert result.exit_code == 0
    assert '### `' in result.output  # Markdown headers

def test_cli_search_json():
    """CLI search returns valid JSON."""
    result = runner.invoke(app, ['search', 'auth', '--format=json'])
    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert 'symbols' in data

def test_cli_blast_radius():
    """CLI blast-radius shows callers + callees."""
    result = runner.invoke(app, ['blast-radius', 'SessionManager.validate_token'])
    assert result.exit_code == 0
    assert 'direct_callers' in result.output or 'Direct callers' in result.output

def test_cli_index_status():
    """CLI index-status shows stats."""
    result = runner.invoke(app, ['index-status'])
    assert result.exit_code == 0
    assert 'files' in result.output.lower() or 'symbols' in result.output.lower()
```

---

## Feature 2: Dead Code Detection

### Goals

1. Find unreferenced functions, classes, methods
2. Framework-aware (ignore routes, controllers, entry points)
3. Export to MCP tool: `find_dead_code()`
4. Export to CLI command: `ast-tools find-dead`

### Algorithm

**Step 1: Build reverse call graph**
```python
# Already have: symbol → callees (who does this call?)
# Need: symbol → callers (who calls this?)

def find_unreferenced_symbols(project_path):
    db = get_db_connection(project_path)
    
    # Get all user-defined symbols (exclude tests, vendor, generated)
    all_symbols = db.query("""
        SELECT id, name, file, kind 
        FROM symbols 
        WHERE kind IN ('function', 'class', 'method')
        AND file NOT LIKE '%/test%'
        AND file NOT LIKE '%/vendor/%'
        AND file NOT LIKE '%/node_modules/%'
    """)
    
    # Get all symbols that are CALLED by something
    called_symbols = db.query("""
        SELECT DISTINCT callee_id
        FROM edges
        WHERE edge_type = 'calls'
    """)
    
    # Unreferenced = all - called
    called_ids = {row['callee_id'] for row in called_symbols}
    unreferenced = [s for s in all_symbols if s['id'] not in called_ids]
    
    return unreferenced
```

**Step 2: Filter false positives**

Exclude:
- ✅ **Entry points:** `main()`, `if __name__ == '__main__'` blocks
- ✅ **Framework conventions:** Flask routes (`@app.route`), Django views, FastAPI endpoints
- ✅ **Magic methods:** `__init__`, `__str__`, `__repr__`, etc. (called implicitly)
- ✅ **Override methods:** Methods that override parent class (called via inheritance)
- ✅ **Test fixtures:** pytest fixtures, unittest test methods
- ✅ **Public API:** Symbols exported via `__all__`

```python
def filter_false_positives(symbols, project_path):
    filtered = []
    for symbol in symbols:
        # Skip magic methods
        if symbol['name'].startswith('__') and symbol['name'].endswith('__'):
            continue
        
        # Skip entry points
        if symbol['name'] in ('main', 'setup', 'run'):
            if is_entry_point(symbol):  # Check if in main module
                continue
        
        # Skip framework routes
        if has_decorator(symbol, ['route', 'view', 'api', 'endpoint']):
            continue
        
        # Skip overrides
        if is_override(symbol):  # Check parent class
            continue
        
        # Skip __all__ exports
        if is_in_all_exports(symbol):
            continue
        
        filtered.append(symbol)
    
    return filtered
```

### MCP Tool Interface

```python
# src/ast_tools/tools/dead_code.py

def _tool_find_dead_code(args: dict[str, Any]) -> dict[str, Any]:
    """Find unreferenced code in the project.
    
    Returns:
        {
            "dead_code": [
                {
                    "symbol": "deprecated_helper",
                    "kind": "function",
                    "file": "src/utils.py",
                    "line": 42,
                    "last_modified": "2026-05-15",
                    "confidence": "high",  # high/medium/low (based on filters)
                }
            ],
            "summary": {
                "total_unreferenced": 23,
                "likely_dead": 12,  # After filtering
                "entry_points_excluded": 5,
                "framework_excluded": 6,
            }
        }
    """
    project_path = Path(args.get("project_path", ".")).resolve()
    include_tests = args.get("include_tests", False)
    
    # Run dead code detection
    unreferenced = find_unreferenced_symbols(project_path)
    filtered = filter_false_positives(unreferenced, project_path)
    
    # Format results
    results = []
    for symbol in filtered:
        results.append({
            "symbol": symbol["name"],
            "kind": symbol["kind"],
            "file": str(Path(symbol["file"]).relative_to(project_path)),
            "line": symbol["line"],
            "confidence": calculate_confidence(symbol),
        })
    
    return {
        "dead_code": results,
        "summary": {
            "total_unreferenced": len(unreferenced),
            "likely_dead": len(filtered),
        }
    }
```

### CLI Integration

```bash
# CLI command
ast-tools find-dead --include-tests --format=markdown

# Example output
## Dead Code Report

### `deprecated_helper()` (function)
**File:** `src/utils.py`:42  
**Confidence:** High  
**Last modified:** 2026-05-15

```python
def deprecated_helper():
    """Old helper function."""
    pass
```

### 12 symbols likely dead
- 5 entry points excluded
- 6 framework routes excluded
```

### Test Plan

```python
# tests/test_dead_code.py

def test_find_dead_code_basic():
    """Find simple unreferenced function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        create_file(tmpdir, "utils.py", '''
def used_function():
    pass

def unused_function():  # This is dead
    pass

def main():
    used_function()
''')
        result = _tool_find_dead_code({"project_path": tmpdir})
        assert len(result["dead_code"]) == 1
        assert result["dead_code"][0]["symbol"] == "unused_function"

def test_skip_magic_methods():
    """Don't flag __init__, __str__ as dead."""
    with tempfile.TemporaryDirectory() as tmpdir:
        create_file(tmpdir, "models.py", '''
class User:
    def __init__(self, name):
        self.name = name
    
    def __str__(self):
        return self.name
''')
        result = _tool_find_dead_code({"project_path": tmpdir})
        # __init__ and __str__ should be excluded
        assert len(result["dead_code"]) == 0

def test_skip_framework_routes():
    """Don't flag Flask routes as dead."""
    with tempfile.TemporaryDirectory() as tmpdir:
        create_file(tmpdir, "routes.py", '''
from flask import Flask
app = Flask(__name__)

@app.route('/users')
def get_users():  # Called by Flask, not in code
    return []
''')
        result = _tool_find_dead_code({"project_path": tmpdir})
        assert len(result["dead_code"]) == 0
```

---

## Implementation Plan

### Week 1: CLI Tool (10 hours)

**Day 1-2: Core CLI (4h)**
- [ ] Create `src/ast_tools/cli.py` with argparse
- [ ] Implement `search` command
- [ ] Implement `nav` command
- [ ] Implement `index-status` command

**Day 3: Formatters (3h)**
- [ ] Create `src/ast_tools/cli/formatters.py`
- [ ] Implement markdown, JSON, tree, compact formats
- [ ] Test formatter output

**Day 4: Commands (3h)**
- [ ] Implement `blast-radius` command
- [ ] Implement `callers` command
- [ ] Implement `callees` command
- [ ] Implement `refresh` command

**Dependencies:** `argparse`, `rich` (for pretty output), `json`

### Week 2: Dead Code Detection (15 hours)

**Day 1-2: Core algorithm (6h)**
- [ ] Create `src/ast_tools/tools/dead_code.py`
- [ ] Implement `find_unreferenced_symbols()`
- [ ] Build reverse call graph query
- [ ] Test basic detection

**Day 3: False positive filtering (5h)**
- [ ] Implement `filter_false_positives()`
- [ ] Exclude magic methods
- [ ] Detect framework decorators (Flask, FastAPI, Django)
- [ ] Detect entry points
- [ ] Detect overrides

**Day 4: MCP + CLI integration (4h)**
- [ ] Register `_tool_find_dead_code()` in `__init__.py`
- [ ] Add CLI command `ast-tools find-dead`
- [ ] Write tests
- [ ] Document in README

**Dependencies:** AST analysis (existing), decorator detection (new)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| CLI commands implemented | 6 (search, nav, blast-radius, callers, callees, index-status) |
| Output formats | 4 (markdown, JSON, tree, compact) |
| Dead code detection accuracy | >80% (20% false positive rate acceptable) |
| False positive exclusions | 5+ categories (magic, entry points, framework, overrides, __all__) |
| Test coverage | >90% for new code |
| Lint violations | 0 (ruff clean) |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CLI arg parsing edge cases | Medium | Low | Use argparse (battle-tested), add input validation |
| Dead code false positives | High | Medium | Conservative filtering, confidence scoring, clear documentation |
| Framework detection complexity | Medium | Medium | Start with Flask/FastAPI only, expand later |
| Performance on large codebases | Low | Low | Optimize SQL queries, add caching |

---

## Next Steps (Per plan-and-audit MEDIUM mode)

1. ✅ **Spec complete** (this document)
2. ⏳ **Forward Audit** — Validate feasibility, check for missing requirements
3. ⏳ **Reverse Audit** — Identify gaps, edge cases, security concerns
4. ⏳ **Synthesis** — Combine audits into final implementation plan
5. ⏳ **Sign-off** — Get user approval before coding
6. ⏳ **TDD Implementation** — Tests first, then code

---

**Status:** READY FOR AUDITS

*Forward and reverse audits should run in parallel (independent, no shared state).*