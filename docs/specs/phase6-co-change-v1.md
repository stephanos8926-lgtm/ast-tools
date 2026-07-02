# Phase 6: Co-Change Analysis — SPEC

**Date:** 2026-07-02
**Author:** Lucien
**Mode:** MEDIUM (new reusable capability, MCP server extension)
**Status:** Pending sign-off

## Executive Summary

**Goal:** Detect and surface code that tends to change together, enabling agents to answer "what else needs updating when I change X?"

**Why Now:**
- Phase 5 (KG) provides static graph queries — Phase 6 adds temporal analysis
- No other MCP code tool offers co-change analysis as a first-class feature
- Critical for safe refactoring: "I changed the API, what implementations need updating?"
- Enables hotspot detection: files with high churn + high coupling = bug magnets

## Architecture

```
src/ast_tools/cochange/         # New package — co-change analysis
├── __init__.py                  # Exports
├── git_miner.py                 # Parse git log, extract co-change pairs
└── hotspot.py                   # Hotspot detection (churn + coupling)

src/ast_tools/tools/co_change.py # 4 MCP tools wrapping co-change analysis

tests/cochange/
├── __init__.py
├── test_git_miner.py
└── test_hotspot.py
```

## Schema Additions (to existing v5 database)

```sql
CREATE TABLE co_change_pairs (
    id INTEGER PRIMARY KEY,
    symbol1_id TEXT NOT NULL,
    symbol2_id TEXT NOT NULL,
    frequency INTEGER DEFAULT 0,     -- How many commits both changed
    avg_gap REAL DEFAULT 0.0,         -- Avg commits between changes
    last_co_change INTEGER,           -- Unix timestamp of last paired change
    coupling REAL DEFAULT 0.0,        -- 0.0 - 1.0 coupling score
    FOREIGN KEY (symbol1_id) REFERENCES symbols(id) ON DELETE CASCADE,
    FOREIGN KEY (symbol2_id) REFERENCES symbols(id) ON DELETE CASCADE
);

CREATE TABLE churn_metrics (
    file_path TEXT PRIMARY KEY,
    commit_count INTEGER DEFAULT 0,
    lines_added INTEGER DEFAULT 0,
    lines_deleted INTEGER DEFAULT 0,
    authors_count INTEGER DEFAULT 0,
    last_modified INTEGER,
    instability REAL DEFAULT 0.0      -- lines_deleted / (lines_added + lines_deleted)
);
```

## Components

### Component 1: GitMiner (`src/ast_tools/cochange/git_miner.py`)

Parses `git log --numstat --format="%H %at %s"` to extract:
- **Co-change pairs**: two files changed in same commit → increment frequency
- **Change gap**: average commits between paired changes (proximity signal)
- **Coupling score**: Jaccard-like: `frequency / (total_commits_for_both - frequency)`
- **Per-file metrics**: commit count, lines added/deleted, authors, last modified

```python
class GitMiner:
    def __init__(self, repo_path: str | Path): ...
    def mine(self, max_commits: int = 5000) -> dict[str, Any]:
        """Parse git log and return co-change pairs + file metrics."""
    def mine_pairs(self, db_path: str | Path) -> int:
        """Mine and store co-change pairs + churn metrics to DB."""
```

### Component 2: Hotspot Detector (`src/ast_tools/cochange/hotspot.py`)

Combines churn metrics with co-change data to find high-risk areas:

```python
def compute_hotspots(
    db_path: str | Path,
    top_n: int = 10
) -> list[dict]:
    """Files with highest (churn * coupling) score."""
```

### Component 3: MCP Tools (`src/ast_tools/tools/co_change.py`)

| Tool | Input | Output |
|------|-------|--------|
| `co_change_predict` | `symbol` or `file_path` | Files/symbols that tend to change with it, sorted by coupling |
| `co_change_hotspots` | `top_n` (int=10) | Hotspots: highest-risk files |
| `co_change_history` | `file_path` | Churn history for a specific file |
| `co_change_diff` | `symbol` | Symbols at risk when changing this symbol |

### Files to Create

| File | Est LOC | Purpose |
|------|---------|---------|
| `src/ast_tools/cochange/__init__.py` | 20 | Package init |
| `src/ast_tools/cochange/git_miner.py` | 300 | Git log parser + co-change pair extraction |
| `src/ast_tools/cochange/hotspot.py` | 100 | Hotspot computation |
| `src/ast_tools/tools/co_change.py` | 250 | 4 MCP tools |
| `tests/cochange/__init__.py` | 0 | Empty |
| `tests/cochange/test_git_miner.py` | 200 | Git miner tests |
| `tests/cochange/test_hotspot.py` | 100 | Hotspot tests |

### Files to Modify

| File | Purpose |
|------|---------|
| `src/ast_tools/tools/__init__.py` | Register 4 new tools |
| `docs/SESSION_STATE.md` | Track progress |

## Acceptance Criteria

- [ ] GitMiner parses `git log --numstat` output correctly
- [ ] Co-change pairs stored with frequency, coupling score, timestamps
- [ ] Churn metrics per file: commits, lines_added/deleted, authors
- [ ] `co_change_predict` returns sorted suggestions for a given file
- [ ] `co_change_hotspots` returns top-N riskiest files
- [ ] `co_change_history` returns per-file churn details
- [ ] `co_change_diff` identifies symbols at risk when changing a symbol
- [ ] All 4 MCP tools registered with correct schemas
- [ ] Tests pass with no regressions in existing suite
- [ ] Total tests >= 30
- [ ] Handles empty repo / no commits gracefully
- [ ] Handles binary files (skip in numstat)
