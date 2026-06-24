# Semantic Database — Phase 1 Implementation Plan

**Version:** 1.0  
**Date:** 2026-06-23  
**Mode:** MEDIUM (plan-and-audit skill)  
**Spec Reference:** `docs/specs/semantic-db-phase1-v1.md`

---

## Overview

**Goal:** Build core indexer library with SQLite persistence, content-hash caching, and 5 new MCP tools.

**Execution Order:** Sequential phases (shared dependencies)

| Phase | Component | Files | Est. Time |
|-------|-----------|-------|-----------|
| **Phase 0** | Prerequisites | Install tree-sitter, create dirs | 5 min |
| **Phase 1** | Database Layer | `database/` (4 files) | 30 min |
| **Phase 2** | Indexer Core | `indexer/` (3 files) | 40 min |
| **Phase 3** | MCP Tools | `tools/` (5 files) | 40 min |
| **Phase 4** | Integration | Server wiring, tests | 30 min |

**Total:** ~2.5 hours (with TDD cycles)

---

## Phase 0: Prerequisites

### Task 0.1: Install tree-sitter Dependencies

**Objective:** Install tree-sitter Python bindings + language grammars.

**Step 1: Install via pip**
```bash
pip install tree-sitter tree-sitter-python tree-sitter-typescript
```

**Step 2: Verify installation**
```bash
python3 -c "import tree_sitter; import tree_sitter_python; print('OK')"
```

**Step 3: Commit**
```bash
git add -A && git commit -m "chore: install tree-sitter dependencies"
```

### Task 0.2: Create Package Directories

**Step 1: Create directories**
```bash
cd ~/Workspaces/ast-tools
mkdir -p src/ast_tools/indexer src/ast_tools/database
mkdir -p tests/indexer tests/database
```

**Step 2: Verify structure**
```bash
find src/ast_tools -type d | sort
```

---

## Phase 1: Database Layer

### Task 1.1: Database Connection Management

**File:** `src/ast_tools/database/connection.py` (NEW)

**Objective:** Create connection factory with WAL mode and proper pragmas.

**Implementation:**
```python
"""Database connection management."""

import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

DEFAULT_DB_PATH = Path.home() / ".cache" / "ast-tools" / "codebase.db"

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Create a connection with optimal pragmas."""
    db_path = db_path or DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Critical pragmas
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA busy_timeout = 5000")  # 5s timeout for locks
    
    return conn

@contextmanager
def database_context(db_path: Optional[Path] = None):
    """Context manager for database connections."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()
```

**Test:** `tests/database/test_connection.py::test_wal_mode_enabled`

---

### Task 1.2: Database Schema + Migrations

**File:** `src/ast_tools/database/schema.py` (NEW)

**Objective:** Define schema with versioning and auto-migration.

**Implementation:**
```python
"""Database schema definition and migrations."""

import sqlite3
from pathlib import Path
from typing import List, Tuple

SCHEMA_VERSION = 1

INITIAL_SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

-- Core symbols table
CREATE TABLE IF NOT EXISTS symbols (
    id TEXT PRIMARY KEY,
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
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT REFERENCES symbols(id),
    target_name TEXT NOT NULL,
    target_id TEXT REFERENCES symbols(id),
    edge_type TEXT CHECK(edge_type IN ('calls','imports','inherits','instantiates')),
    resolution_state INTEGER DEFAULT 0,
    UNIQUE(source_id, target_name, edge_type)
);

-- File cache (content-hash tracking)
CREATE TABLE IF NOT EXISTS file_cache (
    file_path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    last_indexed INTEGER NOT NULL,
    symbol_count INTEGER DEFAULT 0
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_qualified ON symbols(qualified_name);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_file_cache_hash ON file_cache(content_hash);

-- Triggers for FTS5 sync
CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, signature, docstring)
    VALUES (NEW.rowid, NEW.name, NEW.signature, NEW.docstring);
END;

CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, signature, docstring)
    VALUES ('delete', OLD.rowid, OLD.name, OLD.signature, OLD.docstring);
END;

CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, signature, docstring)
    VALUES ('delete', OLD.rowid, OLD.name, OLD.signature, OLD.docstring);
    INSERT INTO symbols_fts(rowid, name, signature, docstring)
    VALUES (NEW.rowid, NEW.name, NEW.signature, NEW.docstring);
END;
"""

def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema."""
    conn.executescript(INITIAL_SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, int(Path.now().timestamp()))
    )
    conn.commit()

def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version."""
    row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
    return row['version'] if row else 0

def needs_migration(conn: sqlite3.Connection) -> bool:
    """Check if migration is needed."""
    return get_schema_version(conn) < SCHEMA_VERSION
```

**Test:** `tests/database/test_schema.py::test_initial_schema_created`

---

### Task 1.3: Query Functions

**File:** `src/ast_tools/database/queries.py` (NEW)

**Objective:** Implement all database query operations.

**Implementation (partial — full file ~400 lines):**
```python
"""Database query functions."""

import sqlite3
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class Symbol:
    id: str
    name: str
    qualified_name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    signature: Optional[str]
    docstring: Optional[str]
    is_public: bool
    content_hash: str

def search_symbols(
    conn: sqlite3.Connection,
    query: str,
    kind: Optional[str] = None,
    limit: int = 20
) -> List[Symbol]:
    """Search symbols using FTS5 + BM25 ranking."""
    sql = """
        SELECT s.* FROM symbols s
        JOIN symbols_fts fts ON s.rowid = fts.rowid
        WHERE fts MATCH ?
        {kind_filter}
        ORDER BY bm25(symbols_fts)
        LIMIT ?
    """
    
    kind_filter = "AND s.kind = ?" if kind else ""
    params = [query] + ([kind] if kind else []) + [limit]
    
    rows = conn.execute(sql.format(kind_filter=kind_filter), params).fetchall()
    return [Symbol(**dict(row)) for row in rows]

def find_symbol_definition(
    conn: sqlite3.Connection,
    name: str
) -> Optional[Symbol]:
    """Find exact symbol definition by name."""
    row = conn.execute(
        "SELECT * FROM symbols WHERE name = ? OR qualified_name = ? LIMIT 1",
        (name, name)
    ).fetchone()
    return Symbol(**dict(row)) if row else None

def list_symbols_by_file(
    conn: sqlite3.Connection,
    file_path: str
) -> List[Symbol]:
    """List all symbols in a file."""
    rows = conn.execute(
        "SELECT * FROM symbols WHERE file_path = ? ORDER BY start_line",
        (file_path,)
    ).fetchall()
    return [Symbol(**dict(row)) for row in rows]

def get_cached_hash(
    conn: sqlite3.Connection,
    file_path: str
) -> Optional[str]:
    """Get cached content hash for a file."""
    row = conn.execute(
        "SELECT content_hash FROM file_cache WHERE file_path = ?",
        (file_path,)
    ).fetchone()
    return row['content_hash'] if row else None

def update_file_cache(
    conn: sqlite3.Connection,
    file_path: str,
    content_hash: str,
    symbol_count: int
) -> None:
    """Update file cache entry."""
    conn.execute("""
        INSERT OR REPLACE INTO file_cache (file_path, content_hash, last_indexed, symbol_count)
        VALUES (?, ?, strftime('%s', 'now'), ?)
    """, (file_path, content_hash, symbol_count))
    conn.commit()

def insert_symbol(
    conn: sqlite3.Connection,
    symbol: Symbol
) -> None:
    """Insert or update a symbol."""
    conn.execute("""
        INSERT OR REPLACE INTO symbols 
        (id, name, qualified_name, kind, file_path, start_line, end_line, 
         signature, docstring, is_public, content_hash, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%s', 'now'))
    """, (symbol.id, symbol.name, symbol.qualified_name, symbol.kind,
          symbol.file_path, symbol.start_line, symbol.end_line,
          symbol.signature, symbol.docstring, symbol.is_public, symbol.content_hash))
    conn.commit()

def insert_edge(
    conn: sqlite3.Connection,
    source_id: str,
    target_name: str,
    edge_type: str,
    target_id: Optional[str] = None
) -> None:
    """Insert an edge (call, import, inherit)."""
    conn.execute("""
        INSERT OR REPLACE INTO edges (source_id, target_name, target_id, edge_type, resolution_state)
        VALUES (?, ?, ?, ?, ?)
    """, (source_id, target_name, target_id, edge_type, 1 if target_id else 0))
    conn.commit()
```

**Test:** `tests/database/test_queries.py::test_search_symbols_fts5`

---

### Task 1.4: Database Package Init

**File:** `src/ast_tools/database/__init__.py` (NEW)

```python
"""Database layer for semantic codebase index."""

from .connection import get_connection, database_context
from .schema import init_schema, get_schema_version, needs_migration
from .queries import (
    Symbol,
    search_symbols,
    find_symbol_definition,
    list_symbols_by_file,
    get_cached_hash,
    update_file_cache,
    insert_symbol,
    insert_edge,
)

__all__ = [
    'get_connection',
    'database_context',
    'init_schema',
    'get_schema_version',
    'needs_migration',
    'Symbol',
    'search_symbols',
    'find_symbol_definition',
    'list_symbols_by_file',
    'get_cached_hash',
    'update_file_cache',
    'insert_symbol',
    'insert_edge',
]
```

---

## Phase 2: Indexer Core

### Task 2.1: Parser Abstraction

**File:** `src/ast_tools/indexer/parser.py` (NEW)

**Objective:** Unified parser interface for Python `ast` + tree-sitter fallback.

**Implementation:**
```python
"""AST parser abstraction."""

import ast
from pathlib import Path
from typing import Optional, Any
import tree_sitter_python as tspython

class Parser:
    """Unified parser for Python code."""
    
    def __init__(self):
        self.ts_language = tspython.language()
    
    def parse_python_ast(self, source: str, filename: str = "<unknown>") -> ast.AST:
        """Parse Python code using stdlib ast module."""
        return ast.parse(source, filename=filename)
    
    def parse_tree_sitter(self, source: bytes) -> Any:
        """Parse using tree-sitter (for future multi-language support)."""
        from tree_sitter import Parser as TSParser
        ts_parser = TSParser()
        ts_parser.set_language(self.ts_language)
        return ts_parser.parse(source)
```

**Test:** `tests/indexer/test_parser.py::test_parse_python_ast`

---

### Task 2.2: Symbol Extractor

**File:** `src/ast_tools/indexer/extractor.py` (NEW)

**Objective:** Extract symbols and edges from parsed AST.

**Implementation (partial):**
```python
"""Symbol and edge extraction from AST."""

import ast
from pathlib import Path
from typing import List, Tuple
from ..database import Symbol

class SymbolExtractor(ast.NodeVisitor):
    """Extract symbols from Python AST."""
    
    def __init__(self, file_path: str, content_hash: str):
        self.file_path = file_path
        self.content_hash = content_hash
        self.symbols: List[Symbol] = []
        self.edges: List[Tuple[str, str, str]] = []  # (source_id, target_name, edge_type)
        self.scope: List[str] = []  # Qualified name stack
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        qualified_name = ".".join(self.scope + [node.name])
        symbol_id = f"{self.file_path}:{qualified_name}"
        
        signature = self._get_signature(node)
        docstring = ast.get_docstring(node)
        
        symbol = Symbol(
            id=symbol_id,
            name=node.name,
            qualified_name=qualified_name,
            kind="function",
            file_path=self.file_path,
            start_line=node.lineno,
            end_line=node.end_lineno,
            signature=signature,
            docstring=docstring,
            is_public=not node.name.startswith("_"),
            content_hash=self.content_hash
        )
        self.symbols.append(symbol)
        
        # Extract calls within function
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()
    
    def visit_ClassDef(self, node: ast.ClassDef):
        # Similar to FunctionDef
        pass
    
    def visit_Import(self, node: ast.Import):
        # Extract import edges
        pass
    
    def visit_Call(self, node: ast.Call):
        # Extract call edges
        if isinstance(node.func, ast.Name):
            self.edges.append((self._current_symbol_id(), node.func.id, "calls"))
        self.generic_visit(node)
    
    def _get_signature(self, node: ast.FunctionDef) -> str:
        """Generate function signature string."""
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)
        return f"def {node.name}({', '.join(args)})"
    
    def _current_symbol_id(self) -> Optional[str]:
        """Get current symbol ID from scope."""
        if self.scope:
            return f"{self.file_path}:{'.'.join(self.scope)}"
        return None

def extract_symbols(file_path: str, content: str, content_hash: str) -> Tuple[List[Symbol], List[Tuple]]:
    """Extract all symbols and edges from a Python file."""
    tree = ast.parse(content, filename=file_path)
    extractor = SymbolExtractor(file_path, content_hash)
    extractor.visit(tree)
    return extractor.symbols, extractor.edges
```

**Test:** `tests/indexer/test_extractor.py::test_extract_function_symbols`

---

### Task 2.3: Pickle Cache

**File:** `src/ast_tools/indexer/cache.py` (NEW)

**Objective:** Content-hash based AST caching with pickle.

**Implementation:**
```python
"""Pickle-based AST caching with content-hash invalidation."""

import hashlib
import pickle
from pathlib import Path
from typing import Optional, Any
import ast

CACHE_DIR = Path.home() / ".cache" / "ast-tools" / "ast-cache"

class ASTCache:
    """Content-hash based AST cache."""
    
    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def _compute_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_cache_path(self, file_path: str, content_hash: str) -> Path:
        """Generate cache file path."""
        safe_path = file_path.replace("/", "_").replace(":", "_")
        return CACHE_DIR / f"{safe_path}.{content_hash[:16]}.pkl"
    
    def get_or_parse(self, file_path: str, content: str) -> ast.AST:
        """Get cached AST or parse and cache."""
        content_hash = self._compute_hash(content)
        cache_path = self._get_cache_path(file_path, content_hash)
        
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except (pickle.PickleError, EOFError):
                cache_path.unlink()  # Corrupted cache
        
        # Parse and cache
        tree = ast.parse(content, filename=file_path)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(tree, f, protocol=pickle.HIGHEST_PROTOCOL)
        except (pickle.PickleError, OSError):
            pass  # Cache write failed, continue without caching
        
        return tree
    
    def invalidate(self, file_path: str):
        """Invalidate all cached ASTs for a file."""
        safe_path = file_path.replace("/", "_").replace(":", "_")
        for cache_file in CACHE_DIR.glob(f"{safe_path}.*.pkl"):
            cache_file.unlink()
```

**Test:** `tests/indexer/test_cache.py::test_cache_hit_on_unchanged_content`

---

### Task 2.4: Indexer Package Init

**File:** `src/ast_tools/indexer/__init__.py` (NEW)

```python
"""Indexer core for semantic codebase analysis."""

from .parser import Parser
from .extractor import SymbolExtractor, extract_symbols
from .cache import ASTCache

__all__ = [
    'Parser',
    'SymbolExtractor',
    'extract_symbols',
    'ASTCache',
]
```

---

## Phase 3: MCP Tools

### Task 3.1: search_symbols Tool

**File:** `src/ast_tools/tools/search_symbols.py` (NEW)

```python
"""MCP tool: search_symbols."""

from typing import Optional
from mcp.types import Tool

from ..database import get_connection, search_symbols as db_search_symbols

TOOL_DEFINITION = Tool(
    name="search_symbols",
    description="Search symbols by name/signature using FTS5 full-text search.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query (supports wildcards)"},
            "kind": {"type": "string", "enum": ["function", "class", "method", "variable", "import", "constant"], "description": "Filter by symbol kind"},
            "limit": {"type": "integer", "default": 20, "description": "Max results"}
        },
        "required": ["query"]
    }
)

async def search_symbols_handler(name: str, arguments: dict) -> list:
    """Handle search_symbols tool call."""
    query = arguments["query"]
    kind = arguments.get("kind")
    limit = arguments.get("limit", 20)
    
    with get_connection() as conn:
        results = db_search_symbols(conn, query, kind, limit)
    
    return [
        {
            "name": r.name,
            "qualified_name": r.qualified_name,
            "kind": r.kind,
            "file_path": r.file_path,
            "start_line": r.start_line,
            "signature": r.signature
        }
        for r in results
    ]
```

**Test:** `tests/tools/test_semantic_tools.py::test_search_symbols_mcp`

---

### Task 3.2: find_symbol_definition Tool

**File:** `src/ast_tools/tools/find_symbol_definition.py` (NEW)

(Pattern identical to Task 3.1, uses `find_symbol_definition` query)

---

### Task 3.3: list_symbols Tool

**File:** `src/ast_tools/tools/list_symbols.py` (NEW)

(Uses `list_symbols_by_file` query)

---

### Task 3.4: index_status Tool

**File:** `src/ast_tools/tools/index_status.py` (NEW)

```python
"""MCP tool: index_status."""

from mcp.types import Tool
from ..database import get_connection

TOOL_DEFINITION = Tool(
    name="index_status",
    description="Get index statistics: indexed file count, cache size, last update.",
    inputSchema={"type": "object", "properties": {}}
)

async def index_status_handler(name: str, arguments: dict) -> dict:
    """Handle index_status tool call."""
    with get_connection() as conn:
        file_count = conn.execute("SELECT COUNT(*) FROM file_cache").fetchone()[0]
        symbol_count = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    
    return {
        "indexed_files": file_count,
        "total_symbols": symbol_count,
        "total_edges": edge_count,
        "cache_path": str(Path.home() / ".cache" / "ast-tools")
    }
```

---

### Task 3.5: refresh_index Tool

**File:** `src/ast_tools/tools/refresh_index.py` (NEW)

```python
"""MCP tool: refresh_index."""

from pathlib import Path
from typing import Optional, List
from mcp.types import Tool
from ..database import get_connection
from ..indexer import extract_symbols, ASTCache

TOOL_DEFINITION = Tool(
    name="refresh_index",
    description="Force reindex files. If file_paths is None, reindex entire codebase.",
    inputSchema={
        "type": "object",
        "properties": {
            "file_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to reindex (None = all)"
            },
            "project_root": {
                "type": "string",
                "description": "Project root directory"
            }
        }
    }
)

async def refresh_index_handler(name: str, arguments: dict) -> dict:
    """Handle refresh_index tool call."""
    file_paths = arguments.get("file_paths")
    project_root = Path(arguments.get("project_root", "."))
    
    if not file_paths:
        # Scan project for Python files
        file_paths = [str(p) for p in project_root.glob("**/*.py") if "__pycache__" not in str(p)]
    
    cache = ASTCache()
    indexed = 0
    errors = []
    
    with get_connection() as conn:
        for file_path in file_paths:
            try:
                content = Path(file_path).read_text()
                # Compute hash
                import hashlib
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                
                # Check if changed
                cached_hash = None  # Implement get_cached_hash call
                if cached_hash == content_hash:
                    continue  # Unchanged, skip
                
                # Parse and extract
                symbols, edges = extract_symbols(file_path, content, content_hash)
                
                # Update DB
                for symbol in symbols:
                    # Implement insert_symbol call
                    pass
                for edge in edges:
                    # Implement insert_edge call
                    pass
                
                indexed += 1
            except Exception as e:
                errors.append({"file": file_path, "error": str(e)})
    
    return {"indexed": indexed, "errors": errors}
```

---

## Phase 4: Integration

### Task 4.1: Wire Tools into Server

**File:** `src/ast_tools/tools/__init__.py` (MODIFY)

Add imports and registrations for 5 new tools.

### Task 4.2: Write Unit Tests

Create test files per phase above. Run:
```bash
PYTHONPATH=src python3 -m pytest tests/indexer/ tests/database/ -v
```

### Task 4.3: Write Integration Tests

```bash
PYTHONPATH=src python3 -m pytest tests/tools/test_semantic_tools.py -v
```

### Task 4.4: Run Full Test Suite

```bash
PYTHONPATH=src python3 -m pytest tests/ -x -q --tb=short
```

### Task 4.5: Final Commit

```bash
git add -A && git commit -m "feat: add semantic database core (Phase 1 complete)"
```

---

## Verification Checklist

- [ ] All new tests pass
- [ ] Existing 114 tests still pass
- [ ] 5 new MCP tools appear in `list_tools()`
- [ ] Database created at `~/.cache/ast-tools/codebase.db`
- [ ] FTS5 search returns results <50ms
- [ ] Incremental reindex skips unchanged files
- [ ] Pickle cache shows speedup on second parse

---

## Rollback Plan

Each phase is one commit. If Phase 1 fails:
```bash
git revert HEAD  # Undo Phase 1
```

---

**Next Step:** Dispatch forward + reverse audits before implementation.