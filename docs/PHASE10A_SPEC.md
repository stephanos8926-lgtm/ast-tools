# Phase 10A: Structural Code Intelligence Enhancements — SPEC

**Date:** 2026-06-25  
**Author:** Lucien  
**Mode:** MEDIUM (5+ files, new reusable capability, MCP server extension)  
**Status:** Pending sign-off  

---

## Executive Summary

**Goal:** Add three new MCP tools to ast-tools for structural code intelligence:
1. `code_validate_syntax` — Multi-language AST validation (Python, JS/TS, Rust, Go, SQL, Shell)
2. `repo_skeleton` — Intelligent project type detection + dependency graph + ASCII tree
3. `file_related_suggest` — Smart "open related files" with AST import analysis + heuristics

**Why Now:**
- rw-agent analysis (SPECIALIZED_COMPONENTS_ANALYSIS.md) identified critical gaps in code validation and project mapping
- Current ast-edit only validates Python via libcst — no multi-language support
- project_info is generic — doesn't detect project type or generate dependency graphs
- Agents constantly need "what files are related?" for navigation

**Impact:**
- Prevents broken code from being written (validation)
- Faster codebase onboarding (project type detection)
- Better agent navigation (related file suggestions)

**Total Effort:** ~1 week (6-9 days)  
**Files to Create:** 4 new tool files + 3 test files + 1 doc  
**Files to Modify:** `tools/__init__.py` (register new tools)

---

## Tool 1: `code_validate_syntax`

### Problem

Current state:
- `ast_edit` validates Python via libcst (Python-only)
- Hermes `code_tools` skill runs terminal linters (ruff, eslint) — subprocess overhead
- No native multi-language validation in ast-tools
- rw-agent has ZERO syntax validation (critical gap)

### Solution

AST-based syntax validation for 6 languages without subprocess overhead.

### Interface Contract

```python
@mcp_tool(
    name="code_validate_syntax",
    description="Validate code syntax for multiple languages using AST parsers. Returns validation errors with line/column positions.",
    inputSchema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Code content to validate"},
            "language": {"type": "string", "enum": ["python", "javascript", "typescript", "rust", "go", "sql", "shell"], "description": "Programming language"},
            "file_path": {"type": "string", "description": "Optional file path for context (e.g., tsconfig.json location for TypeScript)"}
        },
        "required": ["content", "language"]
    }
)
def _tool_code_validate(params: dict[str, Any]) -> dict[str, Any]:
    """
    Validate code syntax without executing it.
    
    Returns:
        {
            "valid": bool,
            "errors": [
                {
                    "line": int,
                    "column": int,
                    "message": str,
                    "error_type": str  # syntax, parse, type_error
                }
            ],
            "warnings": [...],  # Optional warnings (e.g., unused imports)
            "parser_used": str,  # e.g., "ast.parse", "babel", "rustc"
            "duration_ms": float
        }
```

### Implementation Details

**Parsers by Language:**

| Language | Parser | Method | Fallback |
|----------|--------|--------|----------|
| **Python** | `ast.parse()` | Built-in | None |
| **JavaScript** | `@babel/parser` | npm package (optional) | `node --check` (subprocess) |
| **TypeScript** | `typescript` | `tsc --noEmit --skipLibCheck` | None |
| **Rust** | `rustc` | `rustc --emit=metadata -Z no-codegen` | None |
| **Go** | `go` | `go build -o /dev/null` | None |
| **SQL** | `sqlparse` | Python library | None |
| **Shell** | `bash` | `bash -n` | None |

**Key Design Decisions:**

1. **Pure AST validation only** — No linting (ruff, eslint), no style checks
2. **Graceful degradation** — If parser not available, return error with suggestion
3. **No subprocess for Python/SQL** — Pure Python parsers only
4. **Optional subprocess for JS/TS/Rust/Go** — Only if native parser unavailable
5. **Fast failure** — Return immediately on first syntax error (don't collect all)

**Dependencies:**

```toml
# pyproject.toml
[project.optional-dependencies]
validation = [
    "sqlparse>=0.4.4",  # SQL parsing
    # JS/TS/Rust/Go handled via subprocess fallback
]
```

### Files to Create

- `src/ast_tools/tools/code_validate.py` — Main implementation (~150 lines)
- `tests/tools/test_code_validate.py` — Test suite (~100 lines)

### Files to Modify

- `src/ast_tools/tools/__init__.py` — Register new tool
- `pyproject.toml` — Add optional dependencies

### Test Plan

```python
def test_python_valid():
    result = _tool_code_validate({"content": "def foo(): pass", "language": "python"})
    assert result["valid"] is True
    assert len(result["errors"]) == 0

def test_python_invalid():
    result = _tool_code_validate({"content": "def foo( pass", "language": "python"})
    assert result["valid"] is False
    assert len(result["errors"]) == 1
    assert result["errors"][0]["line"] == 1

def test_javascript_valid():
    result = _tool_code_validate({"content": "function foo() { return 42; }", "language": "javascript"})
    assert result["valid"] is True

def test_typescript_invalid():
    result = _tool_code_validate({"content": "const x: number = ", "language": "typescript"})
    assert result["valid"] is False

def test_sql_valid():
    result = _tool_code_validate({"content": "SELECT * FROM users WHERE id = 1;", "language": "sql"})
    assert result["valid"] is True

def test_shell_invalid():
    result = _tool_code_validate({"content": "if [ -f file.txt ; then echo hi", "language": "shell"})
    assert result["valid"] is False
```

---

## Tool 2: `repo_skeleton`

### Problem

Current state:
- `project_info` provides generic file counts + entry points
- No project type detection (Python vs Node vs Go vs Rust)
- No dependency graph visualization
- rw-agent's `explore` is just depth-limited `ls` (dumb file list)
- Agents need "what kind of project is this?" on join

### Solution

Intelligent project skeleton with type detection, key file identification, dependency graph, and ASCII tree.

### Interface Contract

```python
@lcp_tool(
    name="repo_skeleton",
    description="Generate intelligent project skeleton with type detection, key file identification, and dependency graph.",
    inputSchema={
        "type": "object",
        "properties": {
            "root_path": {"type": "string", "description": "Project root directory"},
            "max_depth": {"type": "integer", "default": 5, "description": "Max directory depth to scan"},
            "include_tests": {"type": "boolean", "default": True, "description": "Include test files in output"},
            "include_configs": {"type": "boolean", "default": True, "description": "Include config files"},
            "generate_deps": {"type": "boolean", "default": True, "description": "Generate dependency graph"}
        },
        "required": ["root_path"]
    }
)
def _tool_repo_skeleton(params: dict[str, Any]) -> dict[str, Any]:
    """Generate intelligent project skeleton."""
```

### Output Format

```json
{
  "project_type": "python",
  "confidence": 0.95,
  "detected_indicators": [
    "pyproject.toml",
    "src/ layout",
    "*.py files (89)"
  ],
  "structure": {
    "directories": [
      {"path": "src/ast_tools", "type": "package", "file_count": 23},
      {"path": "tests", "type": "tests", "file_count": 15}
    ],
    "key_files": [
      {"path": "pyproject.toml", "role": "build_config"},
      {"path": "README.md", "role": "documentation"},
      {"path": "src/ast_tools/__init__.py", "role": "entry_point"}
    ],
    "entry_points": [
      "ast_tools_server:main",
      "project_tools:cli_main"
    ],
    "test_files": ["tests/test_e2e.py", "tests/database/test_schema.py"],
    "config_files": ["pyproject.toml", ".gitignore", ".github/workflows/ci.yml"]
  },
  "dependencies": {
    "direct": ["mcp>=1.0.0", "tree-sitter>=0.21.0", "sqlite-vec>=0.1.0"],
    "dev": ["pytest>=7.0.0", "ruff>=0.4.0"],
    "graph": {
      "src/ast_tools": ["mcp", "tree-sitter", "sqlite-vec"],
      "tests": ["pytest"]
    }
  },
  "summary": "Python package (src layout) with 89 Python files, 27 test files. Uses pyproject.toml, pytest, ruff. Entry points: ast_tools_server, project_tools. Dependencies: mcp, tree-sitter, sqlite-vec.",
  "tree_ascii": "ast-tools/\n├── src/\n│   └── ast_tools/\n│       ├── __init__.py\n│       └── ...\n├── tests/\n└── pyproject.toml"
}
```

### Implementation Details

**Project Type Detection:**

```python
PROJECT_INDICATORS = {
    "python": [
        ("pyproject.toml", 3),
        ("setup.py", 2),
        ("requirements.txt", 2),
        ("*.py", 1),
        ("src/", 2),  # src layout bonus
    ],
    "node": [
        ("package.json", 3),
        ("*.js", 1),
        ("*.ts", 1),
        ("node_modules/", 2),
    ],
    "go": [
        ("go.mod", 3),
        ("*.go", 1),
        ("vendor/", 2),
    ],
    "rust": [
        ("Cargo.toml", 3),
        ("*.rs", 1),
        ("src/", 1),
    ],
}
```

**Scoring Algorithm:**

```python
def detect_project_type(root: Path) -> tuple[str, float]:
    scores = defaultdict(float)
    indicators_found = defaultdict(list)
    
    for lang, checks in PROJECT_INDICATORS.items():
        for pattern, weight in checks:
            matches = list(root.glob(pattern)) if "*" in pattern else [root / pattern]
            if any(p.exists() for p in matches):
                scores[lang] += weight
                indicators_found[lang].append(pattern)
    
    if not scores:
        return "unknown", 0.0
    
    winner = max(scores, key=scores.get)
    confidence = min(1.0, scores[winner] / 5.0)  # Normalize to 0-1
    return winner, confidence, indicators_found[winner]
```

**Dependency Parsing:**

Reuse existing `module_imports` logic for Python. For other languages:
- Node: Parse `package.json` → dependencies + devDependencies
- Go: Parse `go.mod` → require block
- Rust: Parse `Cargo.toml` → [dependencies] section

**ASCII Tree Generation:**

```python
def generate_tree(root: Path, max_depth: int = 5) -> str:
    lines = []
    def _scan(path: Path, prefix: str = "", depth: int = 0):
        if depth > max_depth:
            return
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        for i, item in enumerate(items):
            if item.name.startswith('.'):
                continue
            is_last = i == len(items) - 1
            marker = "└── " if is_last else "├── "
            lines.append(f"{prefix}{marker}{item.name}")
            if item.is_dir():
                extension = "    " if is_last else "│   "
                _scan(item, prefix + extension, depth + 1)
    _scan(root)
    return f"{root.name}/\n" + "\n".join(lines)
```

### Files to Create

- `src/ast_tools/tools/repo_skeleton.py` — Main implementation (~250 lines)
- `tests/tools/test_repo_skeleton.py` — Test suite (~150 lines)

### Files to Modify

- `src/ast_tools/tools/__init__.py` — Register new tool
- `pyproject.toml` — No new deps needed (reuse existing)

### Test Plan

```python
def test_python_project_detection():
    result = _tool_repo_skeleton({"root_path": "/home/sysop/Workspaces/ast-tools"})
    assert result["project_type"] == "python"
    assert result["confidence"] > 0.9
    assert "pyproject.toml" in [f["path"] for f in result["structure"]["key_files"]]

def test_node_project_detection(tmp_path):
    # Create fake Node project
    (tmp_path / "package.json").write_text('{"name": "test"}')
    (tmp_path / "src/index.js").write_text("console.log('hi')")
    result = _tool_repo_skeleton({"root_path": str(tmp_path)})
    assert result["project_type"] == "node"

def test_dependency_graph():
    result = _tool_repo_skeleton({"root_path": "/home/sysop/Workspaces/ast-tools", "generate_deps": True})
    assert "dependencies" in result
    assert "mcp" in result["dependencies"]["direct"]
    assert "graph" in result["dependencies"]

def test_ascii_tree():
    result = _tool_repo_skeleton({"root_path": "/home/sysop/Workspaces/ast-tools"})
    assert "tree_ascii" in result
    assert "ast-tools/" in result["tree_ascii"]
    assert "├──" in result["tree_ascii"] or "└──" in result["tree_ascii"]
```

---

## Tool 3: `file_related_suggest`

### Problem

Agents constantly need to navigate related files:
- "Open the test file for this module"
- "What files import this one?"
- "Show me sibling modules in the same package"

Current state:
- rw-agent has basic heuristics (test file patterns, same-dir scan)
- No AST-based import analysis
- ast-tools has `module_imports` but not exposed as "related files" suggestion

### Solution

Smart related file suggestions using AST import analysis + test file heuristics + call graph.

### Interface Contract

```python
@lcp_tool(
    name="file_related_suggest",
    description="Suggest files related to a given file based on imports, test patterns, and directory structure.",
    inputSchema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "File to find related files for"},
            "workspace": {"type": "string", "description": "Project root (optional, defaults to git root)"},
            "max_suggestions": {"type": "integer", "default": 5, "description": "Max results to return"},
            "include_tests": {"type": "boolean", "default": True, "description": "Include test files"},
            "include_imports": {"type": "boolean", "default": True, "description": "Include import relationships"}
        },
        "required": ["file_path"]
    }
)
def _tool_file_related_suggest(params: dict[str, Any]) -> dict[str, Any]:
```

### Output Format

```json
{
  "file": "/home/sysop/Workspaces/ast-tools/src/ast_tools/tools/semantic_search.py",
  "suggestions": [
    {
      "path": "/home/sysop/Workspaces/ast-tools/tests/tools/test_semantic_search_context.py",
      "reason": "test_file",
      "confidence": 0.95,
      "explanation": "Test file matches pattern tests/tools/test_*.py"
    },
    {
      "path": "/home/sysop/Workspaces/ast-tools/src/ast_tools/tools/search_symbols.py",
      "reason": "imports_this",
      "confidence": 0.85,
      "explanation": "Imports search_symbols from this module"
    },
    {
      "path": "/home/sysop/Workspaces/ast-tools/src/ast_tools/database/queries.py",
      "reason": "imported_by",
      "confidence": 0.80,
      "explanation": "This file imports from queries.py"
    },
    {
      "path": "/home/sysop/Workspaces/ast-tools/src/ast_tools/tools/context_tools.py",
      "reason": "sibling",
      "confidence": 0.60,
      "explanation": "Same directory (src/ast_tools/tools/)"
    },
    {
      "path": "/home/sysop/Workspaces/ast-tools/src/ast_tools/embeddings/store.py",
      "reason": "call_graph",
      "confidence": 0.55,
      "explanation": "Called by semantic_search via hybrid_search"
    }
  ]
}
```

### Implementation Details

**Suggestion Strategies (in priority order):**

1. **Test files** (highest priority, 0.9-0.95 confidence)
   - Pattern: `test_<stem>.py`, `<stem>_test.py`, `tests/test_<stem>.py`
   - Check: File exists? → High confidence

2. **Imported by** (0.8-0.9 confidence)
   - Use `module_imports` tool → fan-in (what imports FROM this file)
   - Reuse existing `find_references` for cross-file imports

3. **Imports this** (0.7-0.8 confidence)
   - Use `module_imports` tool → fan-out (what this file imports)
   - Build reverse lookup

4. **Same-directory siblings** (0.5-0.6 confidence)
   - Scan directory, exclude current file
   - Prioritize `.py` files with similar naming

5. **Call graph** (0.5-0.6 confidence)
   - Use `structural_analysis` with `analysis_type="callers"` or `"callees"`
   - Find functions that call functions in this file

6. **Name matching across project** (0.4-0.5 confidence)
   - Same stem in different dirs (e.g., `api/user.py`, `models/user.py`)
   - Glob: `**/{stem}.py`

**Reuse Existing Tools:**

```python
# From module_imports tool
fan_in = module_imports(module="ast_tools.tools.semantic_search")["fan_in"]  # What imports this
fan_out = module_imports(module="ast_tools.tools.semantic_search")["fan_out"]  # What this imports

# From find_references tool
refs = find_references(symbol="hybrid_search")["references"]

# From structural_analysis tool
callers = structural_analysis(symbol="hybrid_search", analysis_type="callers")["callers"]
```

### Files to Create

- `src/ast_tools/tools/file_related.py` — Main Implementation (~180 lines)
- `tests/tools/test_file_related.py` — Test suite (~120 lines)

### Files to Modify

- `src/ast_tools/tools/__init__.py` — Register new tool
- No new dependencies (reuse existing tools)

### Test Plan

```python
def test_test_file_detection():
    result = _tool_file_related_suggest({
        "file_path": "/home/sysop/Workspaces/ast-tools/src/ast_tools/tools/semantic_search.py",
        "include_tests": True
    })
    test_suggestions = [s for s in result["suggestions"] if s["reason"] == "test_file"]
    assert len(test_suggestions) > 0
    assert "test_semantic_search" in test_suggestions[0]["path"]
    assert test_suggestions[0]["confidence"] > 0.9

def test_import_relationships():
    result = _tool_file_related_suggest({
        "file_path": "/home/sysop/Workspaces/ast-tools/src/ast_tools/database/queries.py",
        "include_imports": True
    })
    import_suggestions = [s for s in result["suggestions"] if s["reason"] in ["imports_this", "imported_by"]]
    assert len(import_suggestions) > 0

def test_sibling_detection():
    result = _tool_file_related_suggest({
        "file_path": "/home/sysop/Workspaces/ast-tools/src/ast_tools/tools/ast_grep.py",
        "workspace": "/home/sysop/Workspaces/ast-tools"
    })
    sibling_suggestions = [s for s in result["suggestions"] if s["reason"] == "sibling"]
    assert len(sibling_suggestions) > 0
    assert all("tools/" in s["path"] for s in sibling_suggestions)

def test_max_suggestions_limit():
    result = _tool_file_related_suggest({
        "file_path": "/home/sysop/Workspaces/ast-tools/src/ast_tools/tools/ast_edit.py",
        "max_suggestions": 3
    })
    assert len(result["suggestions"]) <= 3
```

---

## Dependencies Between Tools

```
code_validate_syntax  (NO DEPS — standalone)
repo_skeleton        (NO DEPS — standalone, reuses module_imports internally)
file_related_suggest (DEPENDS ON: module_imports, find_references, structural_analysis)
```

**Execution order:**
1. `code_validate_syntax` (independent)
2. `repo_skeleton` (independent)
3. `file_related_suggest` (depends on existing tools — build last)

---

## Integration Points

### ast-tools MCP Server

All three tools auto-register on server startup via `tools/__init__.py` import.

### Hermes Agent

Hermes will discover these tools automatically via MCP protocol:
- `hermes tools list` → shows new tools
- Available for `delegate_task` subagents
- Available for inline use via `mcp_ast_tools_*` functions

### Existing ast-tools Features

- `code_validate_syntax` → Integrate with `ast_edit` pre-flight validation (optional enhancement)
- `repo_skeleton` → Enhance `project_info` documentation (reference, don't replace)
- `file_related_suggest` → Complement `module_imports` (higher-level abstraction)

---

## Rollback Plan

If any tool causes issues:
1. Comment out registration in `tools/__init__.py`
2. Restart ast-tools server
3. Tools disappear from MCP tool list
4. No breaking changes to existing tools

All tools are additive — no existing behavior modified.

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Test coverage** | >90% | `pytest --cov=src/ast_tools/tools` |
| **Tool latency** | <100ms p95 | `time hermes tools call code_validate_syntax ...` |
| **Validation accuracy** | 100% for Python, >95% for others | Test suite + manual verification |
| **Project detection accuracy** | >90% on known projects | Test on 10+ repos (ast-tools, NexusAgent, FORGE, etc.) |

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Parser dependencies unavailable | Low | Medium | Graceful degradation with error message + suggestion |
| TypeScript/Rust/Go not installed | Medium | Low | Subprocess fallback only — core Python validation still works |
| Large repo scanning slow (repo_skeleton) | Medium | Low | Depth limit (default 5), progress indicator |
| Import analysis circular deps (file_related) | Low | Low | Timeout protection, cycle detection |

---

## Files Summary

### Create (7 files)
```
src/ast_tools/tools/code_validate.py        (~150 lines)
src/ast_tools/tools/repo_skeleton.py        (~250 lines)
src/ast_tools/tools/file_related.py         (~180 lines)
tests/tools/test_code_validate.py           (~100 lines)
tests/tools/test_repo_skeleton.py           (~150 lines)
tests/tools/test_file_related.py            (~120 lines)
docs/PHASE10A_SPEC.md                       (this file)
```

### Modify (1 file)
```
src/ast_tools/tools/__init__.py             (register 3 new tools)
```

### Total New Code
~950 lines (700 implementation + 250 tests)

---

## Next Steps

1. ✅ Spec complete (this document)
2. ⏳ Forward audit — Validate feasibility, identify gaps
3. ⏳ Reverse audit — Find missing considerations
4. ⏳ Synthesis — Combine audits into implementation plan
5. ⏳ User sign-off — Approval before coding
6. ⏳ TDD implementation — Tests first, then code
7. ⏳ Integration testing — Verify tools work in Hermes
8. ⏳ Documentation — Update README, skill docs
9. ⏳ Ship v0.2.0 — Release to GitHub + MCP registry

---

**Status:** Ready for audit → sign-off → implementation