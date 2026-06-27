# Ast-Tools Enhancement Research — God-Tier Code Intelligence

**Date:** 2026-07-24  
**Status:** Research Phase  
**Author:** Lucien (Lead Digital Architect)

---

## Executive Summary

Current ast-tools Phase 2 provides **Python-only** semantic search with vector embeddings. To reach "god-tier" status, we need:

1. **Multi-language support** (C/C++, Rust, Go, JS/TS, etc.)
2. **Real-time indexing** (inotify daemons, file watchers)
3. **LSP integration** (type-aware code intelligence)
4. **Dependency graph tools** (cross-file impact analysis)
5. **LLM curators** (automated index health, staleness detection)
6. **Session context injection** (semantic queries into agent context)

---

## 1. Multi-Language Support via Tree-sitter

### Current State
- `src/ts_backend.py`: Python-only tree-sitter backend (3 functions: `ts_parse`, `ts_grep`, `ts_read`)
- No multi-language support implemented
- Tree-sitter not installed (5 tests skip with `ImportError`)

### Tree-sitter Language Coverage

| Language | Parser | Quality | File Exts | Install |
|----------|--------|---------|-----------|---------|
| **C** | `tree-sitter-c` | ✅ Stable (ABI 15) | `.c`, `.h` | `pip install tree-sitter-c` |
| **C++** | `tree-sitter-cpp` | ✅ Stable (ABI 14) | `.cpp`, `.hpp`, `.cc` | `pip install tree-sitter-cpp` |
| **Rust** | `tree-sitter-rust` | ✅ Stable (ABI 15) | `.rs` | `pip install tree-sitter-rust` |
| **Go** | `tree-sitter-go` | ✅ Stable (ABI 14) | `.go` | `pip install tree-sitter-go` |
| **JavaScript** | `tree-sitter-javascript` | ✅ Stable (ABI 14) | `.js`, `.jsx`, `.mjs` | `pip install tree-sitter-javascript` |
| **TypeScript** | `tree-sitter-typescript` | ✅ Stable (ABI 14) | `.ts`, `.tsx` | `pip install tree-sitter-typescript` |
| **Python** | `tree-sitter-python` | ✅ Stable | `.py` | ✅ Already supported |
| **Java** | `tree-sitter-java` | ✅ Stable (ABI 14) | `.java` | `pip install tree-sitter-java` |
| **Markdown** | `tree-sitter-markdown` | ⚠️ Community | `.md` | `pip install tree-sitter-markdown` |
| **YAML** | `tree-sitter-yaml` | ⚠️ Community | `.yaml`, `.yml` | `pip install tree-sitter-yaml` |
| **JSON** | `tree-sitter-json` | ✅ Stable | `.json` | `pip install tree-sitter-json` |
| **Bash** | `tree-sitter-bash` | ✅ Stable (ABI 14) | `.sh`, `.bash` | `pip install tree-sitter-bash` |

**Total:** 306+ languages available via [tree-sitter-language-pack](https://github.com/kreuzberg-dev/tree-sitter-language-pack) (Rust, 403★)

### Recommended Approach

**Option A: Language Pack (Best)**
```bash
pip install @kreuzberg/tree-sitter-language-pack
# Auto-downloads parsers on first use
# 306 languages, unified API
```

**Option B: Individual Parsers (Control)**
```bash
pip install tree-sitter tree-sitter-python tree-sitter-rust tree-sitter-go \
            tree-sitter-typescript tree-sitter-cpp tree-sitter-javascript
```

### Implementation Plan

1. **Extend `src/ts_backend.py`**
   - Replace `_LANGUAGE_MAP` with dynamic loading
   - Add `ts_grep_lang(pattern, lang)` for cross-language search
   - Add `ts_read_lang(file_path, lang)` for API surface extraction

2. **Add multi-language symbol extraction**
   - Currently: Python-only `extract_symbols()` in `src/ast_tools/indexer/extractor.py`
   - Need: Generic `extract_symbols_ts(tree, lang)` for all languages

3. **Update schema**
   - `symbols.lang` field (currently `NULL`) → store language code
   - Enable per-language filtering in `semantic_search()`

**Estimated effort:** 8-12 tool calls (2-3 hours)

---

## 2. Real-Time Indexing with File Watchers

### Current State
- **No automatic reindexing** — manual `refresh_index()` only
- Index becomes stale immediately after edits
- No daemon/cronjob/watchdog pattern

### Industry Patterns (2025-2026)

#### Pattern 1: Kestr (High-Performance Daemon, C++)
- **Repo:** [Pomilon/Kestr](https://github.com/Pomilon/Kestr)
- **Features:**
  - Linux inotify / macOS FSEvents / Windows ReadDirectoryChangesW
  - Tree-sitter parsing (10 languages)
  - SQLite Vector storage
  - HTTP + MCP interface
  - Queue-based debouncing (100ms window)
- **Lessons:**
  - Watch at project root, recurse into subdirs
  - Debounce rapid saves (IDEs write 3-5x per save)
  - Queue → Worker → Embed → Store pipeline
  - Status dashboard (queue size, memory, progress)

#### Pattern 2: Vector-Indexer-MCP (Python Daemon)
- **Repo:** [davidgut1982/vector-indexer-mcp](https://github.com/davidgut1982/vector-indexer-mcp)
- **Features:**
  - `watchdog` library (cross-platform inotify wrapper)
  - SQLAlchemy + pgvector (PostgreSQL)
  - MCP server with 7 tools
  - `systemctl --user` integration
- **Architecture:**
```
File System → Watcher (inotify) → Queue (debounce) → Worker (chunk+embed) → Vector DB → MCP Server
```
- **Config:**
```yaml
watcher:
  watch_paths:
    - /srv/myproject
  exclude_patterns:
    - __pycache__
    - .git
    - venv
    - "*.log"
  include_extensions:
    - .py
    - .md
    - .json
  debounce_ms: 100
  batch_size: 50
```

#### Pattern 3: GrepAI Watch (Go Daemon)
- **Repo:** [yoanbernabeu/grepai](https://yoanbernabeu.github.io/grepai/watch-guide/)
- **Features:**
  - Initial full scan + real-time updates
  - Symbol extraction + call graph
  - RPG (Retrieval-Primed Generation) graph bootstrap
  - PostgreSQL or Gob file storage
- **Key Insight:** Atomic full rewrite of index every 5 seconds (rate-limited)

#### Pattern 4: AstralBrowser Realtime Indexer (Python + inotify)
- **Repo:** [naggie/astralbrowser](https://github.com/naggie/astralbrowser/blob/main/astralbrowser-realtime-indexer)
- **Features:**
  - `inotify.adapters.InotifyTree` (auto-watches new subdirs)
  - Rate-limited full index rewrite (5s coalescing)
  - Background thread with graceful shutdown
- **Simplicity:** Single file, 200 LOC

### Recommended Approach for Ast-Tools

**Phase 1: Python Watcher (Simple)**
```python
# ~/.hermes/scripts/ast-tools-watcher.py
import inotify.adapters
from pathlib import Path

def watch_project(root_path: str):
    i = inotify.adapters.InotifyTree(root_path)
    for event in i.event_gen(yield_nones=False):
        (_, type_names, path, filename) = event
        if filename.endswith('.py') and 'IN_CLOSE_WRITE' in type_names:
            # File saved → reindex
            reindex_file(f"{path}/{filename}")
```

**Phase 2: Hermes Integration**
- Register as Hermes plugin: `~/.hermes/plugins/ast-tools-watcher/`
- Tools: `watch_add`, `watch_remove`, `watch_status`, `reindex_path`
- Cron hook: Reindex every 15 min (stale detection)

**Phase 3: Systemd Service (Production)**
```ini
# ~/.config/systemd/user/ast-tools-watcher.service
[Unit]
Description=Ast-Tools Realtime Indexer

[Service]
ExecStart=/home/sysop/Workspaces/ast-tools/.venv/bin/python \
          /home/sysop/.hermes/scripts/ast-tools-watcher.py
Restart=always

[Install]
WantedBy=default.target
```

**Estimated effort:** 15-20 tool calls (4-5 hours)

---

## 3. LSP Integration — Type-Aware Code Intelligence

### Why LSP?

**Current limitation:** Ast-tools treats code as **text** (AST + embeddings). LSP knows **types**.

**Example:**
```python
def process_user(user: UserDTO) -> Response:
    return api.call(user)
```

**Ast-tools sees:** `"process_user function takes user parameter"`  
**LSP knows:** `UserDTO = {id: UUID, name: str, email: Email}`, `Response = TypedDict`, `api.call = HTTP POST /users`

### LSP Ecosystem (2026)

| Language | Server | Install | Features |
|----------|--------|---------|----------|
| **Python** | `pyright-langserver` | `pip install pyright` | Types, references, call hierarchy |
| **Rust** | `rust-analyzer` | `cargo install rust-analyzer` | 🏆 Gold standard |
| **TypeScript** | `typescript-language-server` | `npm i -g typescript-language-server` | Full TS intelligence |
| **Go** | `gopls` | `go install golang.org/x/tools/gopls` | Google-maintained |
| **C/C++** | `clangd` | `apt install clangd` | LLVM foundation |
| **Java** | `eclipse.jdt.ls` | Complex (Eclipse-based) | Full JDT |

### LSP-MCP Bridges

#### Option 1: `lsp-mcp` (Quinten Kasteel)
- **Repo:** [quintenkasteel/lsp-mcp](https://github.com/quintenkasteel/lsp-mcp)
- **Tools:** 14 LSP tools (hover, definition, references, type_definition, implementation, call_hierarchy, etc.)
- **Auto-detect:** Python, Rust, TS, Go, Ruby, Elm, OCaml, Elixir
- **Approach:** Spawns LSP server as subprocess, JSON-RPC over stdio

#### Option 2: `lsp-intelligence` (Peri Levy)
- **Repo:** [perilevy/lsp-intelligence](https://github.com/perilevy/lsp-intelligence)
- **Tools:** 29 MCP tools, TypeScript-only
- **Features:** Root cause trace, impact trace, semantic diff, API guard, gather_context
- **Unique:** Bundles `@ast-grep/napi` for structural search

#### Option 3: `karellen-lsp-mcp` (C/C++ Focus)
- **Repo:** [karellen/karellen-lsp-mcp](https://github.com/karellen/karellen-lsp-mcp)
- **Features:** Multi-session shared daemon, refcounted LSP instances
- **Tools:** 20+ LSP tools, call trees, type trees

#### Option 4: `lsp-mcp-server` (ProfessioneIT)
- **Repo:** [ProfessioneIT/lsp-mcp-server](https://github.com/ProfessioneIT/lsp-mcp-server)
- **Tools:** 29 tools, 10 languages
- **Features:** Multi-root workspace, push-based diagnostics, dry-run rename

### Recommended Approach

**Option A: Build Ast-Tools Native LSP Bridge**
```python
# src/ast_tools/lsp_client.py
import subprocess
import json

class LSPClient:
    def __init__(self, server_cmd: str, root_path: str):
        self.proc = subprocess.Popen(
            server_cmd.split(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )
        self._send("initialize", {"rootUri": f"file://{root_path}"})
    
    def goto_definition(self, file: str, line: int, col: int):
        return self._send("textDocument/definition", {
            "textDocument": {"uri": f"file://{file}"},
            "position": {"line": line-1, "character": col}
        })
    
    def find_references(self, file: str, line: int, col: int):
        return self._send("textDocument/references", ...)
    
    def hover(self, file: str, line: int, col: int):
        return self._send("textDocument/hover", ...)
```

**New MCP Tools:**
- `lsp_definition(file, line, col)` → Where is this symbol defined?
- `lsp_references(file, line, col)` → Where is this used?
- `lsp_hover(file, line, col)` → Type signature + docs
- `lsp_call_hierarchy(file, line, col)` → Who calls this? What does it call?
- `lsp_type_hierarchy(file, line, col)` → Base classes / derived classes
- `lsp_diagnostics(file)` → Compiler errors/warnings

**Option B: Use Existing `lsp-mcp` (Faster)**
```bash
tokrepo install <uuid-for-lsp-mcp>
# Auto-detects pyright, rust-analyzer, etc.
```

**Recommendation:** **Option A** for deep integration with ast-tools semantic DB. Combine LSP type info with vector embeddings = **ultimate code intelligence**.

**Estimated effort:** 20-25 tool calls (6-8 hours) for Option A

---

## 4. Dependency & Cross-File Analysis Tools

### Current State
- `impact_analysis(target)` ✅ — Uses reverse dependency graph
- `module_imports(module)` ✅ — Fan-in/fan-out analysis
- `find_references(symbol)` ✅ — Cross-file refs
- **Missing:** Real dependency chains, transitive impacts, externals detection

### Enhancement Opportunities

#### Tool 1: `dependency_chain(symbol)` — Full Transitive Graph
```python
def dependency_chain(symbol: str, direction: str = "both", depth: int = 3):
    """
    Returns full dependency tree:
    
    {
      "symbol": "process_user",
      "depends_on": [
        {"symbol": "UserDTO", "file": "types.py", "depth": 1},
        {"symbol": "validate_email", "file": "utils.py", "depth": 1,
         "depends_on": [{"symbol": "EMAIL_REGEX", "file": "constants.py", "depth": 2}]
        }
      ],
      "used_by": [
        {"symbol": "handle_signup", "file": "handlers.py", "depth": 1},
        {"symbol": "api_router", "file": "main.py", "depth": 2}
      ]
    }
    """
```

#### Tool 2: `circular_dependencies()` — Detect Import Cycles
```python
def circular_dependencies(project_root: str):
    """
    Finds circular imports (A→B→A anti-pattern).
    
    Returns:
    [
      {"cycle": ["auth.py", "user.py", "auth.py"], "severity": "high"},
      {"cycle": ["utils.py", "helpers.py", "validators.py", "utils.py"], "severity": "medium"}
    ]
    """
```

#### Tool 3: `external_dependencies()` — Third-Party Detection
```python
def external_dependencies(file: str):
    """
    Extracts all third-party imports (not stdlib, not local).
    
    Returns:
    {
      "file": "src/handlers.py",
      "externals": [
        {"module": "requests", "line": 5, "symbols": ["get", "post"]},
        {"module": "pydantic", "line": 7, "symbols": ["BaseModel", "Field"]}
      ]
    }
    """
```

#### Tool 4: `dead_code_detection()` — Unused Symbols
```python
def dead_code_detection(project_root: str, entry_points: list[str]):
    """
    Finds symbols defined but never used.
    
    Uses:
    - LSP references (if available)
    - Ast-tools `find_references` fallback
    - Entry point tracing (main, CLI, API routes)
    
    Returns:
    {
      "dead_functions": [
        {"name": "legacy_auth", "file": "auth.py:45", "confidence": 0.95}
      ],
      "dead_classes": [...],
      "dead_variables": [...]
    }
    """
```

#### Tool 5: `api_surface_diff(old_commit, new_commit)` — Contract Changes
```python
def api_surface_diff(old: str, new: str):
    """
    Compares public API between commits.
    
    Returns:
    {
      "added": ["new_function", "NewClass"],
      "removed": ["deprecated_func"],
      "changed": [
        {"symbol": "process_user", "old_sig": "(user)", "new_sig": "(user, options)"}
      ],
      "breaking_changes": [
        {"symbol": "authenticate", "reason": "removed required param 'token'"}
      ]
    }
    """
```

**Estimated effort:** 15-20 tool calls (4-5 hours) for all 5 tools

---

## 5. LLM Curator Service — Index Health Daemon

### Concept
Background LLM agent that **curates** the semantic DB:

1. **Staleness Detection** — Finds symbols without embeddings
2. **Contradiction Resolution** — Duplicate symbols, conflicting signatures
3. **Quality Scoring** — Which embeddings are low-confidence?
4. **Auto-Reindexing** — Re-indexes files changed >7 days ago
5. **Index Compaction** — Removes dead symbols (deleted files)
6. **Context Summarization** — Generates project summaries for agent context

### Architecture

```python
# ~/.hermes/scripts/ast-tools-curator.py

class LLmCurator:
    def __init__(self):
        self.db = get_connection()
        self.llm = get_curator_model()  # Cheap model: Gemma-4-31b
    
    def daily_audit(self):
        """Run every night at 3 AM via cron."""
        report = {
            "total_symbols": self.count_symbols(),
            "missing_embeddings": self.find_missing_embeddings(),
            "stale_files": self.find_stale_files(days=7),
            "contradictions": self.find_contradictions(),
            "dead_symbols": self.find_dead_code()
        }
        
        # Auto-fix simple issues
        self.backfill_embeddings(report["missing_embeddings"])
        self.remove_dead_symbols(report["dead_symbols"])
        
        # Report complex issues to user
        if report["contradictions"]:
            self.send_report(report)
    
    def generate_project_summary(self):
        """Creates AGENTS.md-style summary for fresh sessions."""
        symbols = self.get_top_level_symbols()
        prompt = f"""
        Given these symbols from a Python project:
        {symbols}
        
        Generate a 500-token project summary covering:
        - Architecture overview
        - Key modules
        - Entry points
        - Patterns observed
        """
        return self.llm.generate(prompt)
```

### Cron Integration

```yaml
# ~/.hermes/config.yaml
cron:
  jobs:
    - name: "ast-tools curator"
      schedule: "0 3 * * *"  # 3 AM daily
      script: "~/.hermes/scripts/ast-tools-curator.py --daily-audit"
      deliver: "local"  # Save to ~/.hermes/cron/output/
    
    - name: "ast-tools project summary"
      schedule: "0 8 * * 1"  # Monday 8 AM
      script: "~/.hermes/scripts/ast-tools-curator.py --generate-summary"
```

### Hermes Skill Integration

```markdown
# Skill: ast-tools-curator
When starting a session on a project:
1. Check if `.ast-tools/summary.md` exists and is <7 days old
2. If yes, load it into context
3. If no/stale, run `ast_tools_curator_summary()` tool
```

**Estimated effort:** 10-15 tool calls (3-4 hours)

---

## 6. Session Context Injection

### Problem
Every session starts **blind** — no knowledge of the codebase structure.

### Solution: Semantic Context Injection

#### Hook 1: Session Start
```yaml
# ~/.hermes/hooks/on-session-start
command: |
  if [ -f "$PWD/.ast-tools/summary.md" ]; then
    cat "$PWD/.ast-tools/summary.md" >> "$HERMES_CONTEXT_FILE"
  fi
```

#### Hook 2: File Open Awareness
When user references a file:
```python
# ~/.hermes/plugins/ast-tools-context/plugin.py

@hook("pre_tool_call")
def inject_file_context(tool, args):
    if tool == "read_file":
        file_path = args["path"]
        # LSP: Get type definitions
        types = lsp_get_type_definitions(file_path)
        # Ast-tools: Get semantic neighbors
        neighbors = semantic_search_similar(file_path, k=3)
        # Inject into context
        append_context(f"\n## Related to {file_path}:\n{types}\n{neighbors}")
```

#### Tool: `gather_context(symbols, budget=4000)`
```python
def gather_context(entry_symbols: list[str], token_budget: int = 4000):
    """
    For working on feature X, gather all relevant context.
    
    Args:
        entry_symbols: ["handle_signup", "UserDTO", "AuthService"]
        token_budget: 4000
    
    Returns:
        Concatenated file contents, sorted by relevance, up to budget.
        Marks files as:
        - MUST_READ: Entry symbols + direct dependencies
        - SHOULD_READ: Transitive deps (depth 2)
        - OPTIONAL: Related symbols (semantic similarity)
    """
```

#### Subagent Context Packaging
```python
@hook("pre_delegate_task")
def package_subagent_context(goal, project_root):
    """
    Before spawning subagent:
    1. Parse goal for symbols/tasks
    2. Run gather_context()
    3. Inject into subagent context
    4. Add semantic DB connection path
    """
    symbols = extract_symbols_from_goal(goal)
    ctx = gather_context(symbols, budget=6000)
    context = f"{goal}\n\n## Project Context:\n{ctx}"
    return context
```

**Estimated effort:** 8-12 tool calls (2-3 hours)

---

## 7. Semantic Database Improvements

### Current Schema (v3)
```sql
-- Symbols
CREATE TABLE symbols (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,  -- function, class, method, etc.
    signature TEXT,
    docstring TEXT,
    file_path TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    embedding_hash TEXT  -- For change detection
);

-- Vector embeddings (sqlite-vec virtual table)
CREATE VIRTUAL TABLE symbols_vec USING vec0(
    symbol_id TEXT PRIMARY KEY,
    embedding FLOAT[384]
);

-- File cache
CREATE TABLE file_cache (
    file_path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    symbol_count INTEGER,
    last_indexed INTEGER
);
```

### Enhancement 1: Symbol Metadata Enrichment

```sql
ALTER TABLE symbols ADD COLUMN parameters JSON;     -- ["user: UserDTO", "options: dict"]
ALTER TABLE symbols ADD COLUMN return_type TEXT;    -- "Response"
ALTER TABLE symbols ADD COLUMN decorators JSON;     -- ["@api.route", "@login_required"]
ALTER TABLE symbols ADD COLUMN imports JSON;        -- ["requests", "pydantic.BaseModel"]
ALTER TABLE symbols ADD COLUMN visibility TEXT;     -- "public", "private", "protected"
ALTER TABLE symbols ADD COLUMN complexity INTEGER;  -- Cyclomatic complexity
ALTER TABLE symbols ADD COLUMN test_coverage REAL;  -- 0.0 - 1.0 (from coverage.py)
ALTER TABLE symbols ADD COLUMN last_modified INTEGER;
ALTER TABLE symbols ADD COLUMN git_authors TEXT;    -- ["alice", "bob"]
```

**Why:**
- Filter by visibility → search only public APIs
- Filter by complexity → find complex functions to refactor
- Filter by test coverage → identify untested code
- Track authors → blame for code review

### Enhancement 2: Temporal Edges

```sql
CREATE TABLE edges_temporal (
    source_id TEXT,
    target_id TEXT,
    edge_type TEXT,
    valid_from INTEGER,  -- When this relationship started (git commit time)
    valid_to INTEGER,    -- When it was removed (NULL if still valid)
    commit_hash TEXT
);
```

**Why:** Track how dependencies evolve over time. "When did `process_user` start calling `validate_email`?"

### Enhancement 3: Cross-Project Indexing

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,      -- UUID
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    language TEXT,
    last_indexed INTEGER
);

-- Add project_id to symbols
ALTER TABLE symbols ADD COLUMN project_id TEXT REFERENCES projects(id);
```

**Why:** Search across multiple projects (monorepo support, microservices).

### Enhancement 4: Embedding Improvements

**Current:** `all-MiniLM-L6-v2` (384-dim, generic code+text)

**Better Options:**

| Model | Dim | Training | Speed | Quality |
|-------|-----|----------|-------|---------|
| `all-MiniLM-L6-v2` | 384 | General | ⚡ Fast | Good |
| `bge-small-en-v1.5` | 384 | General | ⚡ Fast | Better |
| `bge-base-en-v1.5` | 768 | General | 🐌 Medium | Best |
| `code-bge-small` | 384 | Code-only | ⚡ Fast | Best for code |
| `instructor-large` | 1024 | Instruction-tuned | 🐌 Slow | SOTA |

**Recommendation:** Offer **dual embeddings**:
- `bge-small-en-v1.5` for general search
- `code-bge-small` for code-specific queries

**Schema:**
```sql
CREATE VIRTUAL TABLE symbols_vec_general USING vec0(
    symbol_id TEXT PRIMARY KEY,
    embedding FLOAT[384]  -- bge-small-en-v1.5
);

CREATE VIRTUAL TABLE symbols_vec_code USING vec0(
    symbol_id TEXT PRIMARY KEY,
    embedding FLOAT[384]  -- code-bge-small
);
```

**Query-time fusion:**
```python
def hybrid_search(query, k=10):
    emb_general = generate_embedding(query, model="bge-small-en-v1.5")
    emb_code = generate_embedding(query, model="code-bge-small")
    
    results_general = search_vec(emb_general, k=k*2)
    results_code = search_vec(emb_code, k=k*2)
    
    # RRF fusion
    return reciprocal_rank_fusion([results_general, results_code], k=k)
```

### Enhancement 5: Incremental Embedding Updates

**Current:** `refresh_index(embeddings=true)` backfills ALL symbols

**Better:** Track embedding staleness

```sql
ALTER TABLE file_cache ADD COLUMN embedding_hash TEXT;

-- Only regenerate if code changed
def smart_backfill():
    stale = conn.execute("""
        SELECT f.file_path, s.id, s.signature, s.docstring
        FROM file_cache f
        JOIN symbols s ON f.file_path = s.file_path
        WHERE f.content_hash != f.embedding_hash
           OR s.embedding_hash IS NULL
    """)
    for file, symbol_id, sig, doc in stale:
        text = f"{sig} {doc}"
        emb = generate_embedding(text)
        insert_embedding(symbol_id, emb)
        update_embedding_hash(symbol_id, hash(text))
```

**Estimated effort:** 12-18 tool calls (3-5 hours) for all enhancements

---

## 8. Priority Roadmap

### Phase 3: Multi-Language Support (2-3 hours)
- [ ] Install tree-sitter-language-pack or individual parsers
- [ ] Extend `ts_backend.py` with multi-language support
- [ ] Add `extract_symbols_ts(tree, lang)` generic extractor
- [ ] Update schema: `symbols.lang` field
- [ ] Add per-language filtering to `semantic_search()`
- [ ] Test suite for 5 languages (Python, Rust, Go, TS, C++)

### Phase 4: Real-Time Indexing (4-5 hours)
- [ ] Build `ast-tools-watcher.py` (inotify daemon)
- [ ] Debounce + queue system
- [ ] Hermes plugin registration
- [ ] Systemd service file
- [ ] Tools: `watch_add`, `watch_status`, `reindex_path`

### Phase 5: LSP Bridge (6-8 hours)
- [ ] Build `lsp_client.py` (LSP over stdio)
- [ ] Integrate pyright for Python
- [ ] New MCP tools: `lsp_definition`, `lsp_references`, `lsp_hover`, etc.
- [ ] Fuse LSP types with semantic embeddings
- [ ] Test with real Python projects

### Phase 6: Dependency Graph Tools (4-5 hours)
- [ ] `dependency_chain(symbol, depth=3)`
- [ ] `circular_dependencies()`
- [ ] `external_dependencies()`
- [ ] `dead_code_detection()`
- [ ] `api_surface_diff(old, new)`

### Phase 7: LLM Curator (3-4 hours)
- [ ] Build `ast-tools-curator.py`
- [ ] Daily cron job (3 AM audit)
- [ ] Auto-backfill embeddings
- [ ] Auto-remove dead symbols
- [ ] Generate project summaries

### Phase 8: Context Injection (2-3 hours)
- [ ] Session start hook (load summary)
- [ ] File open hook (inject related context)
- [ ] `gather_context(symbols, budget)` tool
- [ ] Subagent context packaging hook

### Phase 9: Schema Enhancements (3-5 hours)
- [ ] Add metadata fields (parameters, return_type, decorators, etc.)
- [ ] Dual embeddings (general + code-specific)
- [ ] Incremental embedding updates
- [ ] Migration v3→v4

---

## Conclusions & Recommendations

### Must-Have (God-Tier Foundation)
1. **Multi-language tree-sitter** — Non-negotiable for "universal code intelligence"
2. **Real-time watcher daemon** — Index must stay fresh automatically
3. **LLM curator** — Self-healing index, auto-repair, staleness detection

### High-Value (AI Agent Superpowers)
4. **LSP integration** — Type-aware queries beat text-only search
5. **Context injection hooks** — Agents start sessions with knowledge
6. **Dependency graph tools** — Impact analysis, circular deps, dead code

### Nice-to-Have (Polish)
7. **Schema enrichments** — Metadata, dual embeddings, temporal tracking

---

## Next Steps

**Ask Steven:**
1. Which phase to tackle first? (Recommend: Phase 3 → 4 → 7 → 5 → 6 → 8 → 9)
2. LSP bridge: Build native (Option A) or use `lsp-mcp` (Option B)?
3. Preferred embedding model upgrade? (Stay MiniLM vs dual bge/code-bge)
4. Daemon deployment: User systemd service or background process?

---

## References

- [Tree-sitter Language Pack](https://github.com/kreuzberg-dev/tree-sitter-language-pack) — 306 languages
- [Kestr](https://github.com/Pomilon/Kestr) — C++ daemon, best-in-class architecture
- [LSP-MCP](https://github.com/quintenkasteel/lsp-mcp) — 14 LSP tools
- [LSP-Intelligence](https://github.com/perilevy/lsp-intelligence) — 29 tools, TypeScript-focused
- [GrepAI Watch Guide](https://yoanbernabeu.github.io/grepai/watch-guide/) — Real-time indexing patterns
- [sqlite-vec](https://github.com/asg017/sqlite-vec) — Vector search in SQLite