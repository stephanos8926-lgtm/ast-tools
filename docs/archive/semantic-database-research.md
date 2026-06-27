# Semantic Database Research — Codebase Indexing Solutions

**Date:** 2026-06-23  
**Project:** ast-tools  
**Purpose:** Research foundation for semantic-database extension

---

## Executive Summary

Research across 6 key areas (indexing tools, SQLite best practices, file watchers, caching, Hermes plugins, MCP integration) reveals a clear path forward:

**Recommended approach:** Build a lightweight SQLite-based symbol indexer that:
- Uses Python `ast` for deep Python analysis + tree-sitter for multi-language
- Implements SHA256 content-hash invalidation with pickle caching
- Integrates directly with existing ast-tools infrastructure (not a separate CLI)
- Exposes indexed data via MCP tools using FastMCP pattern
- Watches files via watchdog for incremental updates

**Key differentiator:** Not a standalone tool, but an extension that leverages ast-tools' existing 11 tools (structural_analysis, find_references, impact_analysis).

---

## 1. Competitive Landscape — Existing Code Indexing Tools

### QuickAST (v0.3.1, MIT)
- **Tech:** Python `ast` module + SQLite
- **Features:** Watchdog file watching, call graphs, route detection
- **Limitations:** Python-only, no MCP integration, standalone CLI

### codebase-index (v1.1.0, MIT)
- **Tech:** Tree-sitter (10 languages), SQLite FTS5
- **Features:** Hybrid retrieval (BM25 + vector), MCP server
- **Limitations:** Tree-sitter less precise than `ast` for Python-specific features

### codelibrarian (AGPL 3.0)
- **Tech:** Python `ast` + tree-sitter (8 langs), SQLite + sqlite-vec
- **Features:** Embeddings, Mermaid diagrams
- **Limitations:** AGPL license (viral), embedding overhead for simple symbol lookup

### Serena (LSP-based)
- **Tech:** Language Server Protocol
- **Features:** Symbol-level editing, cross-file navigation
- **Limitations:** Requires LSP server running, not AST-based, no persistence

### SCIP/Sourcegraph
- **Tech:** Enterprise protocol, language-specific indexers
- **Features:** Precise cross-repo navigation, web UI
- **Limitations:** Enterprise-focused, heavy, not embeddable

### **Our Differentiation:**
- Direct integration with ast-tools (leverages existing 11 tools)
- Not a separate CLI — extends MCP server
- Lightweight: single SQLite file, minimal deps
- Hybrid: Python `ast` for depth + tree-sitter for breadth

---

## 2. SQLite Best Practices for Symbol Databases

### Schema Design Patterns

**FTS5 for Full-Text Search:**
```sql
CREATE VIRTUAL TABLE symbols_fts USING fts5(
    name, signature, docstring,
    content=''  -- contentless = halve storage
);
```

**BM25 Ranking:**
- Lower score = better match
- Use `bm25(symbols_fts)` in ORDER BY

**Covering Indexes:**
```sql
CREATE INDEX idx_symbols_file_path 
ON symbols(file_path, name, kind);
```
Includes both WHERE columns + SELECT columns → index-only scan.

**Partial Indexes:**
```sql
CREATE INDEX idx_symbols_public 
ON symbols(name) 
WHERE is_public = 1;
```

**WAL Mode:**
```sql
PRAGMA journal_mode = WAL;
```
Enables write concurrency (critical for file watcher updates).

**WITHOUT ROWID:**
```sql
CREATE TABLE symbols (
    id TEXT PRIMARY KEY,
    ...
) WITHOUT ROWID;
```
For compact primary keys (symbol IDs).

### Performance Validation

Always use `EXPLAIN QUERY PLAN`:
```sql
EXPLAIN QUERY PLAN
SELECT * FROM symbols WHERE file_path = ? AND kind = 'function';
```

Look for: `SEARCH ... USING INDEX` (not `SCAN`).

---

## 3. File Watching Libraries

### watchdog (v6.0.0, 7.3K stars) ✅ **WINNER**

**Pros:**
- Cross-platform: Linux (inotify), macOS (FSEvents/kqueue), Windows (ReadDirectoryChangesW)
- Native API backends → low overhead
- Polling fallback for unsupported systems
- Simple API: `FileSystemEventHandler` + `Observer`

**Cons:**
- Fires multiple events per edit (needs debouncing)
- No built-in recursive filtering by pattern

**Usage Pattern:**
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CodebaseHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            # Debounce + reindex
            pass

observer = Observer()
observer.schedule(CodebaseHandler(), path='.', recursive=True)
observer.start()
```

### Alternatives (Rejected)

- **pyinotify:** Linux-only, deprecated
- **fswatch:** External binary, extra dependency
- **WatchFiles:** Python 3.7+, polling-based, slower

---

## 4. Pickle-based Caching Patterns for AST

### Content-Hash Invalidation Pattern

**Key insight:** Cache key = `(file_path, content_hash, python_version)`

```python
import hashlib, pickle

def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()

def get_or_parse(file_path: str) -> ast.AST:
    content = Path(file_path).read_text()
    content_hash = compute_hash(content)
    cache_key = f"{file_path}:{content_hash}:{sys.version}"
    
    if cache_key in cache:
        return cache[cache_key]
    
    # Parse and cache
    tree = ast.parse(content, filename=file_path)
    cache[cache_key] = tree
    return tree
```

### Performance Benchmarks

**astroid (PyLint's AST library):**
- AST pickle: 50x speedup (50ms → 1ms)
- cached_property for transitive walks: 98% hit rate, -10% overall perf

**Nuitka (Python compiler):**
- Cache dir: `~/.cache/nuitka/`
- Metadata sidecar: `.meta` file with format version
- Format versioning: Invalidate on AST format changes

### Best Practices

1. **Store pickled AST objects, not full node trees** (smaller, faster)
2. **Include Python version in cache key** (AST format changes between versions)
3. **Invalidate on content hash change, not mtime** (mtime unreliable in git ops)
4. **Persist cache to disk** (not just in-memory)

---

## 5. Hermes Plugin Architecture

### Plugin Discovery

**Plugin locations:**
- `~/.hermes/plugins/<name>/` (global)
- `.hermes/plugins/` (project-local)
- pip entry-points (if installed as package)

### Registration API

```python
# In plugin's __init__.py
def register(ctx):
    ctx.register_tool("index_codebase", index_codebase_handler)
    ctx.register_tool("refresh_index", refresh_index_handler)
    ctx.register_tool("index_status", index_status_handler)
```

### MCP Integration

**Config in `~/.hermes/config.yaml`:**
```yaml
mcp_servers:
  codebase-index:
    command: ["python3", "-m", "codebase_index_server"]
    cwd: "~/Workspaces/ast-tools"
```

**Hermes auto-discovers:**
- Tools from `ctx.register_tool()` calls
- CLI commands from `ctx.register_cli_command()`
- Hooks from `pre_tool_call`, `post_tool_call` events

### Extension Points

1. **Tools:** `ctx.register_tool(name, handler)`
2. **CLI:** `ctx.register_cli_command(name, handler)`
3. **Hooks:** `pre_tool_call`, `post_tool_call`, `on_session_end`
4. **Platforms:** Custom adapters (Telegram, Discord, etc.)
5. **Backends:** Custom model providers

---

## 6. MCP Tool Integration Patterns

### FastMCP Pattern ✅ **RECOMMENDED**

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("codebase-index")

@mcp.tool(name="search_symbols")
def search_symbols(
    query: str,
    kind: str | None = None,
    limit: int = 20
) -> list[dict]:
    """Search symbols by name/signature.
    
    Args:
        query: Search query (supports wildcards)
        kind: Filter by symbol kind (function, class, etc.)
        limit: Max results
    """
    # Implementation
    return results
```

**Benefits:**
- Automatic JSON Schema generation from type hints
- Docstrings become tool descriptions
- Pydantic models for complex params: `model_json_schema()`
- Async support (sync tools run in threadpool)

### Tool Annotations (MCP Spec)

```python
@mcp.tool(
    name="search_symbols",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
```

### Context Injection

```python
from mcp.server import Context

@mcp.tool()
async def index_file(path: str, ctx: Context):
    await ctx.log("info", f"Indexing {path}")
    await ctx.report_progress(0.5)
    # Implementation
```

---

## 7. Recommended Architecture for ast-tools

### Database Schema

```sql
-- Core symbols table
CREATE TABLE symbols (
    id TEXT PRIMARY KEY,  -- "file_path:qualified_name"
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('function','class','method','variable','import','constant')),
    file_path TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    signature TEXT,
    docstring TEXT,
    is_public INTEGER DEFAULT 1,
    content_hash TEXT NOT NULL,
    indexed_at INTEGER NOT NULL
);

-- FTS5 for fast name/search
CREATE VIRTUAL TABLE symbols_fts USING fts5(
    name, signature, docstring,
    content=''
);

-- Edges (calls, imports, inherits)
CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT REFERENCES symbols(id),
    target_name TEXT NOT NULL,
    target_id TEXT REFERENCES symbols(id),
    edge_type TEXT CHECK(edge_type IN ('calls','imports','inherits','instantiates')),
    resolution_state INTEGER DEFAULT 0,  -- 0=unresolved, 1=resolved, 2=stale
    UNIQUE(source_id, target_name, edge_type)
);

-- File cache (content-hash tracking)
CREATE TABLE file_cache (
    file_path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    last_indexed INTEGER NOT NULL,
    symbol_count INTEGER DEFAULT 0
);

-- Indexes
CREATE INDEX idx_symbols_file ON symbols(file_path);
CREATE INDEX idx_symbols_name ON symbols(name);
CREATE INDEX idx_symbols_qualified ON symbols(qualified_name);
CREATE INDEX idx_edges_source ON edges(source_id);
CREATE INDEX idx_edges_target ON edges(target_id);
CREATE INDEX idx_file_cache_hash ON file_cache(content_hash);
```

### Directory Structure

```
ast-tools/
├── src/ast_tools/
│   ├── indexer/          # NEW: Core indexing logic
│   │   ├── __init__.py
│   │   ├── parser.py     # AST + tree-sitter parsing
│   │   ├── extractor.py  # Symbol/edge extraction
│   │   └── cache.py      # Pickle cache + content-hash
│   ├── database/         # NEW: SQLite layer
│   │   ├── __init__.py
│   │   ├── schema.py     # Schema + migrations
│   │   ├── queries.py    # Query functions
│   │   └── connection.py # Connection management
│   ├── watcher/          # NEW: File watching
│   │   ├── __init__.py
│   │   └── observer.py   # watchdog integration
│   └── tools/            # EXISTING: 11 tools
│       └── ...
└── src/ast_tools_server.py
```

### MCP Tools to Expose

1. **`search_symbols(query, kind=None, limit=20)`** — FTS5 + BM25
2. **`find_symbol_definition(name)`** — Exact match lookup
3. **`find_references(symbol_name)`** — Uses edges table + ast-grep fallback
4. **`callers(symbol_name, depth=3)`** — Traverse calls edges
5. **`callees(symbol_name, depth=3)`** — Traverse calls edges (reverse)
6. **`impact_analysis(symbol_name, transitive=True)`** — Integrate with existing impact_analysis tool
7. **`list_symbols(file_path)`** — All symbols in a file
8. **`index_status()`** — Cache stats, indexed file count, last update
9. **`refresh_index(file_paths=None)`** — Force reindex (None = all)

### Incremental Indexing Workflow

```python
def index_file(file_path: str) -> SymbolSet:
    content = Path(file_path).read_text()
    content_hash = compute_hash(content)
    
    # Check cache
    cached = db.get_cached(file_path)
    if cached and cached.content_hash == content_hash:
        return cached.symbols  # Skip, unchanged
    
    # Parse + extract
    tree = parse_file(file_path)
    symbols = extract_symbols(tree, file_path)
    edges = extract_edges(tree, symbols)
    
    # Update DB
    db.update_symbols(symbols, content_hash)
    db.update_edges(edges)
    
    return symbols
```

---

## 8. Implementation Risks & Mitigations

### Risk 1: Circular Imports
- **Mitigation:** Use local imports in function bodies, create shared base module

### Risk 2: SQLite Lock Contention
- **Mitigation:** WAL mode, queue-based writes from watcher, read-heavy optimization

### Risk 3: Watchdog Event Storms
- **Mitigation:** Debounce (200ms), batch reindexing, ignore __pycache__/\.git/

### Risk 4: Memory Growth from Pickle Cache
- **Mitigation:** LRU eviction, TTL-based cleanup, disk-backed cache

### Risk 5: Tree-sitter Parser Drift
- **Mitigation:** Pin tree-sitter versions per language, test against known corpus

---

## 9. Next Steps

**Phase 1 (Core Indexer Library):**
1. Create `src/ast_tools/indexer/` with parser, extractor, cache
2. Create `src/ast_tools/database/` with schema, queries, connection
3. Write tests with isolated temp DBs
4. Benchmark: index time for 10K LOC codebase

**Phase 2 (Hermes Plugin):**
1. Create `~/.hermes/plugins/codebase-index/`
2. Implement watchdog observer with debouncing
3. Register tools: `index_codebase`, `refresh_index`, `index_status`

**Phase 3 (MCP Integration):**
1. Add 9 new MCP tools to `ast_tools_server.py`
2. Wire tools into database query layer
3. Test integration with existing tools (impact_analysis, find_references)

---

## 10. References

- **QuickAST:** https://github.com/quickast-dev/quickast
- **codebase-index:** https://github.com/codebao11/codebase-index
- **codelibrarian:** https://github.com/anielokachukwu/codelibrarian
- **watchdog:** https://github.com/gorakhargosh/watchdog
- **FastMCP:** https://github.com/jlowin/fastmcp
- **astroid caching:** https://github.com/PyCQA/astroid
- **Nuitka cache:** https://github.com/Nuitka/Nuitka

---

**End of Research**