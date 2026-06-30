# New Tool Concepts for ast-tools

**Generated:** 2026-06-25  
**Source:** SPECIALIZED_COMPONENTS_ANALYSIS.md from rw-agent project  
**Analysis:** Gap analysis between rw-agent capabilities and ast-tools

---

## Executive Summary

After reviewing the rw-agent specialized components analysis, I identified **7 new tool concepts** that would significantly enhance ast-tools' capabilities. These tools fill gaps in:

1. **Code parsing and merging** (critical gap)
2. **Memory/persistence** (missing entirely)
3. **Conversation/session management** (not applicable to ast-tools)
4. **Repo intelligence** (partial coverage)

**Priority Ranking:**
- 🔴 **High Priority (implement now):** 3 tools
- 🟡 **Medium Priority (next quarter):** 3 tools
- 🟢 **Low Priority (nice to have):** 1 tool

---

## New Tool Concepts

### 🔴 HIGH PRIORITY

#### 1. `code_validate_syntax` — Syntax Validation Before Write

**Inspired by:** Enhanced Code Parser section (Critical gap in rw-agent)

**Purpose:** Validate code syntax before applying changes. Prevents broken code from being written.

**Why ast-tools needs this:**
- `ast_edit` currently validates via libcst (Python-only)
- No validation for other languages (JS/TS, Rust, Go, etc.)
- No pre-flight syntax check for LLM-generated code
- rw-agent has NO syntax validation (critical gap we can fill)

**Implementation:**
```python
# src/ast_tools/tools/code_validate.py
def _tool_code_validate(params: dict[str, Any]) -> dict[str, Any]:
    """
    Validate code syntax for multiple languages.
    
    Parameters:
        content: str — Code to validate
        language: str — Language (python, javascript, typescript, rust, go, sql)
        file_path: Optional[str] — For context-aware validation
    
    Returns:
        {
            "valid": bool,
            "errors": [{"line": int, "column": int, "message": str}],
            "warnings": [...],
            "suggestions": [...]
        }
    """
```

**Features:**
- ✅ Python: `ast.parse()`
- ✅ JavaScript/TypeScript: ESLint parser (if available) or `node --check`
- ✅ Rust: `rustc --emit=metadata`
- ✅ Go: `go build -o /dev/null`
- ✅ SQL: sqlparse validation
- ✅ Shell: `bash -n`

**Integration:**
- Called automatically by `ast_edit` before applying changes
- Available as standalone tool for LLM output validation
- Pre-flight check for `write_file` operations

**Effort:** 2-3 days  
**Impact:** 🔴 Critical — prevents broken code

---

#### 2. `code_merge_blocks` — Intelligent Code Block Merging

**Inspired by:** Enhanced Code Parser — partial code block merging (rw-agent missing)

**Purpose:** Merge LLM-generated code blocks into existing files intelligently (not just full replacement).

**Why ast-tools needs this:**
- Current `ast_edit` requires explicit operations (rename, replace_node, etc.)
- LLMs often output "lazy" code blocks (partial functions, appended methods)
- No automatic detection of merge strategy
- rw-agent only does full file replacement (lossy)

**Implementation:**
```python
# src/ast_tools/tools/code_merge.py
def _tool_code_merge(params: dict[str, Any]) -> dict[str, Any]:
    """
    Merge code blocks into existing file with intelligent strategy detection.
    
    Parameters:
        file_path: str — Target file
        code_blocks: list[dict] — Code blocks with optional markers
        strategy: Optional[str] — Force strategy (replace_all, replace_symbol, append, range)
        dry_run: bool — Preview without applying
    
    Returns:
        {
            "success": bool,
            "merged_content": str,
            "diff": str,
            "strategy_used": str,
            "blocks_merged": int,
            "errors": [...]
        }
    """
```

**Merge Strategies (auto-detected):**
1. **REPLACE_ALL** — Full file replacement (```FULL_FILE marker)
2. **REPLACE_SYMBOL** — Function/class replacement (signature match)
3. **REPLACE_RANGE** — Line-range replacement (@@ -start,+end @@ markers)
4. **APPEND** — Append to end of file
5. **INSERT_AFTER** — Insert after specific symbol
6. **REJECT** — Cannot safely merge (return error)

**Marker Support:**
- Markdown code blocks: ```python ... ```
- SEARCH/REPLACE blocks
- Line-range markers: `@@ -42,+10 @@`
- Function signatures: `def foo(...):`
- Explicit markers: `# FULL_FILE`, `# APPEND`

**Integration:**
- Used by LLM agents for refactoring tasks
- Safer alternative to `write_file` for partial changes
- Syntax validation before applying (calls `code_validate_syntax`)

**Effort:** 4-5 days  
**Impact:** 🔴 High — enables safe incremental edits

---

#### 3. `repo_skeleton` — Intelligent Project Mapping

**Inspired by:** Repo Mapping / Project Skeleton (rw-agent has basic `explore` only)

**Purpose:** Generate intelligent project skeleton with type detection, key file identification, and dependency graph.

**Why ast-tools needs this:**
- Current `project_info` is good but generic
- No project type detection (Python vs Node vs Go)
- No key file identification strategy
- rw-agent's `explore` is depth-limited file list (dumb)
- We can do better with AST + heuristics

**Implementation:**
```python
# src/ast_tools/tools/repo_skeleton.py
def _tool_repo_skeleton(params: dict[str, Any]) -> dict[str, Any]:
    """
    Generate intelligent project skeleton with type detection.
    
    Parameters:
        root_path: str — Project root
        max_depth: int — Max directory depth (default: 5)
        include_tests: bool — Include test files (default: true)
        include_configs: bool — Include config files (default: true)
        generate_deps: bool — Generate dependency graph (default: true)
    
    Returns:
        {
            "project_type": str,  # "python", "node", "go", "rust", "mixed"
            "confidence": float,  # 0.0-1.0
            "structure": {
                "directories": [...],
                "key_files": [...],
                "entry_points": [...],
                "test_files": [...],
                "config_files": [...]
            },
            "dependencies": {
                "direct": [...],
                "dev": [...],
                "graph": [...]  # If generate_deps=true
            },
            "summary": str,  # One-paragraph description
            "tree_ascii": str  # ASCII tree representation
        }
    """
```

**Features:**
- ✅ **Project type detection:**
  - Python: setup.py, pyproject.toml, requirements.txt, *.py
  - Node: package.json, node_modules, *.js/ts
  - Go: go.mod, *.go, vendor/
  - Rust: Cargo.toml, *.rs
  - Mixed: Multiple indicators

- ✅ **Key file identification:**
  - README, LICENSE, CHANGELOG
  - Entry points (main.py, index.js, cmd/)
  - Config files (.envrc, docker-compose.yml)
  - CI/CD configs (.github/, .gitlab-ci.yml)

- ✅ **Dependency graph:**
  - Parse requirements.txt, package.json, go.mod, Cargo.toml
  - Build import graph for Python/JS/Go/Rust
  - Identify circular dependencies

- ✅ **Summary generation:**
  - "Python FastAPI project with 42 files, 12 test files, postgres dependency"
  - Entry points, test framework, database layer

**Integration:**
- First command when joining new codebase
- Complements `codebase_summary` (architecture) with filesystem view
- Output used by agents for context injection

**Effort:** 3-4 days  
**Impact:** 🟡 High — much better than rw-agent's explore

---

### 🟡 MEDIUM PRIORITY

#### 4. `agent_memory_create` — Persistent Memory Storage

**Inspired by:** Memory Skill (MCP-equivalent, rw-agent missing)

**Purpose:** Persistent memory service for cross-session context, entity tracking, and knowledge graphs.

**Why ast-tools needs this:**
- Current session context is ephemeral
- No cross-session memory
- Semantic DB indexes code, not agent knowledge
- rw-agent mentions this as a gap
- Hermes has Honcho (external), but we can build native optional memory

**Implementation:**
```python
# src/ast_tools/tools/memory.py
def _tool_memory_create(params: dict[str, Any]) -> dict[str, Any]:
    """Create or update memory entity."""
    
def _tool_memory_search(params: dict[str, Any]) -> dict[str, Any]:
    """Search memories by query."""
    
def _tool_memory_link(params: dict[str, Any]) -> dict[str, Any]:
    """Create relation between entities."""
```

**Schema:**
```sql
CREATE TABLE memory_entities (
    id INTEGER PRIMARY KEY,
    name TEXT,
    entity_type TEXT,  -- 'person', 'project', 'concept', 'decision', 'code_pattern'
    content TEXT,
    confidence REAL,   -- 0.0-1.0
    ttl_hours INTEGER, -- Optional expiration
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE memory_relations (
    id INTEGER PRIMARY KEY,
    from_entity_id INTEGER,
    to_entity_id INTEGER,
    relation_type TEXT,  -- 'depends_on', 'implements', 'author_of', 'related_to'
    weight REAL DEFAULT 1.0,
    FOREIGN KEY (from_entity_id) REFERENCES entities(id),
    FOREIGN KEY (to_entity_id) REFERENCES entities(id)
);
```

**Use Cases:**
- "Remember that Steven prefers pytest over unittest"
- "This project uses FastAPI + postgres pattern"
- "Decision made on 2026-07-24: use sqlite-vec over chromadb"
- Cross-session context for recurring projects

**Integration:**
- Optional plugin (not enabled by default)
- LLM extracts memories from conversations
- Searchable via semantic similarity

**Effort:** 3-4 days  
**Impact:** 🟡 Medium — nice to have, not critical

---

#### 5. `conversation_export` — Session Export & Recovery

**Inspired by:** Session Manager `/export`, `/resume` commands (rw-agent partial)

**Purpose:** Export ast-tools sessions, analysis results, and conversation history.

**Why ast-tools needs this:**
- Current sessions are ephemeral
- No way to share analysis results
- No audit trail for enterprise users
- rw-agent has this as high priority gap

**Implementation:**
```python
# src/ast_tools/tools/conversation_export.py
def _tool_conversation_export(params: dict[str, Any]) -> dict[str, Any]:
    """
    Export session history and analysis results.
    
    Parameters:
        session_id: str — Session to export
        format: str — markdown, json, pdf (via markdown-pdf)
        include_analysis: bool — Include tool outputs
        include_code: bool — Include code snippets
        output_path: Optional[str] — Save to file
    
    Returns:
        {
            "exported": bool,
            "output_path": str,
            "format": str,
            "size_bytes": int,
            "sections": [...]
        }
    """
```

**Formats:**
- **Markdown:** Human-readable with code blocks
- **JSON:** Machine-readable for replay
- **PDF:** Professional reports (via markdown-pdf)

**Integration:**
- Enterprise audit requirements
- Knowledge sharing between team members
- Backup/restore of analysis sessions

**Effort:** 2 days  
**Impact:** 🟡 Medium — enterprise feature

---

#### 6. `file_related_suggest` — Smart File Suggestions

**Inspired by:** rw-agent's `suggest_related_files()` (good heuristic, we can enhance)

**Purpose:** Suggest related files based on current file (test files, siblings, imports).

**Why ast-tools needs this:**
- rw-agent has basic version (test patterns, siblings)
- We can enhance with AST-based import analysis
- Helps agents navigate codebases faster

**Implementation:**
```python
# src/ast_tools/tools/file_related.py
def _tool_file_related_suggest(params: dict[str, Any]) -> dict[str, Any]:
    """
    Suggest files related to current file.
    
    Parameters:
        file_path: str — Current file
        workspace: Optional[str] — Project root
        max_suggestions: int — Max results (default: 5)
        include_tests: bool — Include test files (default: true)
        include_imports: bool — Include imported files (default: true)
    
    Returns:
        {
            "suggestions": [
                {
                    "path": str,
                    "reason": str,  # "test_file", "imported_by", "imports_this", "sibling"
                    "confidence": float  # 0.0-1.0
                }
            ]
        }
    """
```

**Suggestion Strategies:**
1. **Test files** — test_foo.py, foo_test.py, tests/test_foo.py
2. **Import relationships** — files this imports, files that import this
3. **Same-directory siblings** — Other files in same directory
4. **Name matching** — Same stem in different dirs (api/user.py, models/user.py)
5. **Call graph** — Files in same call chain

**Integration:**
- Auto-suggest when reading a file
- Agent navigation assistance
- "Open related files" pattern

**Effort:** 1-2 days  
**Impact:** 🟡 Medium — QoL improvement

---

### 🟢 LOW PRIORITY

#### 7. `plugin_register` — External Plugin System

**Inspired by:** MCP hot-reload, plugin architecture (rw-agent mentions as Tier 2)

**Purpose:** Allow external tools to register with ast-tools dynamically.

**Why ast-tools might want this:**
- MCP servers can't be hot-reloaded
- Custom tools per project
- Enterprise extensions
- NOT urgent — built-in tools cover 95% of needs

**Implementation:**
```python
# src/ast_tools/plugins/loader.py
def _tool_plugin_register(params: dict[str, Any]) -> dict[str, Any]:
    """
    Register external plugin.
    
    Parameters:
        plugin_path: str — Path to plugin (.py file or directory)
        auto_enable: bool — Auto-enable on load
    
    Returns:
        {
            "registered": bool,
            "tools_added": [...],
            "errors": [...]
        }
    """
```

**Plugin API:**
```python
# Example plugin: my_custom_tool.py
def register_tools(register_tool):
    register_tool('my_custom_analysis', my_custom_handler)

def my_custom_handler(params: dict) -> dict:
    # Custom logic
    return {"result": "..."}
```

**Integration:**
- Enterprise custom analyses
- Project-specific tools
- Experimental features

**Effort:** 3-4 days  
**Impact:** 🟢 Low — nice to have, not urgent

---

## Implementation Priority

### Phase 10A: Code Safety & Merging (2 weeks)
1. ✅ `code_validate_syntax` — Prevent broken code
2. ✅ `code_merge_blocks` — Intelligent merging
3. ✅ `repo_skeleton` — Intelligent project mapping

### Phase 10B: Memory & Navigation (2 weeks)
4. 🔄 `agent_memory_create` — Persistent memory
5. 🔄 `file_related_suggest` — Smart suggestions
6. 🔄 `conversation_export` — Session export

### Phase 10C: Extensibility (1 week)
7. 🔄 `plugin_register` — Plugin system

---

## Comparison with ast-tools Current Tools

| New Tool | Similar Existing | Gap Filled |
|----------|------------------|------------|
| `code_validate_syntax` | None (ast_edit is Python-only) | Multi-language validation |
| `code_merge_blocks` | `ast_edit` (explicit ops) | Auto-detect merge strategy |
| `repo_skeleton` | `project_info` (generic) | Type detection + smart summary |
| `agent_memory_create` | None | Cross-session memory |
| `conversation_export` | None | Audit trail, sharing |
| `file_related_suggest` | None (rw-agent has basic) | AST-based + heuristics |
| `plugin_register` | None | Extensibility |

---

## Recommended Next Steps

1. **Implement `code_validate_syntax`** (2-3 days)
   - Python first (ast.parse)
   - Add JS/TS, Go, Rust incrementally
   - Integrate with `ast_edit` pre-flight

2. **Implement `repo_skeleton`** (3-4 days)
   - Project type detection
   - Key file identification
   - Dependency graph for Python/Node
   - ASCII tree generation

3. **Implement `code_merge_blocks`** (4-5 days)
   - Marker detection
   - Strategy auto-detection
   - AST-based symbol replacement
   - Dry-run preview

4. **Ship Phase 10A as v0.2.0** (Total: 2 weeks)

5. **Evaluate Phases 10B/10C** based on user feedback

---

## Files to Create

```
src/ast_tools/tools/code_validate.py       # Syntax validation
src/ast_tools/tools/code_merge.py          # Intelligent merging
src/ast_tools/tools/repo_skeleton.py       # Project mapping
src/ast_tools/tools/memory.py              # Persistent memory
src/ast_tools/tools/conversation_export.py # Export sessions
src/ast_tools/tools/file_related.py        # Related file suggestions
src/ast_tools/plugins/loader.py            # Plugin system
tests/tools/test_code_validate.py
tests/tools/test_code_merge.py
tests/tools/test_repo_skeleton.py
tests/tools/test_memory.py
docs/PHASE10_NEW_TOOLS.md
```

---

**Generated by:** Lucien (ast-tools analysis)  
**Date:** 2026-06-25  
**Review with:** Steven Page