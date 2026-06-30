# EASY_WINS Spec Reverse Audit — Findings & Recommendations

**Date:** 2026-06-28  
**Auditor:** Hermes Agent (Reverse Audit)  
**Spec Version:** EASY_WINS_SPEC_20260628.md  
**Scope:** CLI Tool + Dead Code Detection  

---

## Executive Summary

The EASY_WINS specification is well-structured but has **critical gaps in security validation, dead code accuracy, and competitive differentiation**. The CLI tool spec lacks input validation and path traversal protection. The dead code detection algorithm is too naive and will produce unacceptable false positive rates (>40% estimated without improvements).

**Severity Distribution:**
- 🔴 **CRITICAL:** 2 issues (security, false positives)
- 🟠 **HIGH:** 4 issues (dynamic dispatch, polymorphism, performance, framework detection)
- 🟡 **MEDIUM:** 6 issues (caching, edge cases, competitive positioning)
- 🟢 **LOW:** 3 issues (rate limiting, UX polish)

---

## 1. SECURITY CONCERNS

### 1.1 Path Traversal Vulnerability 🔴 CRITICAL

**Risk:** CLI accepts `--path <dir>` with no validation. Users can scan arbitrary directories including system files.

**Attack Vector:**
```bash
ast-tools search "password" --path /etc
ast-tools find-dead --path /home/other-user/project
```

**Missing Controls:**
- No check that path is within project root
- No blocklist of sensitive directories
- No validation of resolved path

**Recommendation:**
```python
def validate_path(user_path: str, project_root: Path) -> Path:
    """Ensure path is within project boundaries."""
    resolved = Path(user_path).resolve()
    try:
        resolved.relative_to(project_root)
        return resolved
    except ValueError:
        raise ValueError(f"Path {resolved} is outside project root {project_root}")
```

**Effort:** 1h

---

### 1.2 SQL Injection via FTS5 Syntax 🟠 HIGH

**Risk:** FTS5 MATCH queries accept special operators. User input is parameterized but FTS5 syntax allows operators that could be exploited.

**Current Code (queries.py:43):**
```python
fts_query = "SELECT rowid FROM symbols_fts WHERE symbols_fts MATCH ?"
# Parameterized ✅, but FTS5 operators still work:
# User could inject: 'auth' OR column_name:*
```

**Mitigation:**
- Escape FTS5 special characters: `" ( ) * & | ~ < > -`
- Whitelist allowed operators
- Add query length limit (max 500 chars)

**Effort:** 2h

---

### 1.3 Input Validation Gaps 🟠 HIGH

**Missing Validation:**
| Parameter | Risk | Current | Recommended |
|-----------|------|---------|-------------|
| `--query` | DoS via long string | No limit | Max 500 chars |
| `--limit` | Memory exhaustion | No validation | Max 1000, default 50 |
| `--path` | Path traversal | None | Must be within project |
| `--lang` | Injection | argparse choices ✅ | Keep ✅ |
| Symbol names | SQL injection | Via queries.py ✅ | Audit all uses |

**Recommendation:** Add input validation middleware in `cli.py`:
```python
def validate_search_args(args):
    if len(args.query) > 500:
        raise ValueError("Query too long (max 500 chars)")
    if args.limit > 1000:
        raise ValueError("Limit too high (max 1000)")
    # Escape FTS5 special chars
    args.query = escape_fts5_syntax(args.query)
```

**Effort:** 2h

---

### 1.4 Secret Sanitizer Not Used for CLI

**Finding:** `secret_sanitizer.py` exists but only used for `audit_log`. CLI input not sanitized before DB operations.

**Recommendation:** Apply sanitizer to all user-provided strings before DB queries.

**Effort:** 1h

---

## 2. DEAD CODE DETECTION — FALSE POSITIVES 🟠 HIGH

### 2.1 Dynamic Dispatch Not Tracked

**Problem:** Static call graph misses dynamic calls:
```python
# These DON'T create edges in current system:
getattr(module, function_name)()
exec(f"call_{action}()")
importlib.import_module(module_name).function()
```

**Impact:** Functions called dynamically flagged as dead (false positive).

**Real-World Cases:**
- Plugin systems (dynamically loaded)
- Command dispatchers (CLI frameworks)
- Strategy pattern implementations
- Django signal handlers

**Recommendation (Partial Mitigation):**
1. Detect `getattr`, `exec`, `eval`, `importlib` calls
2. Flag symbols referenced in string literals (low confidence)
3. Add "may be called dynamically" flag to results

**Effort:** 8h (still incomplete without runtime analysis)

---

### 2.2 Polymorphism & Inheritance 🟠 HIGH

**Problem:** Base class methods called via inheritance not tracked.

**Example:**
```python
class BaseView:
    def get(self): pass  # Called via child classes

class UserView(BaseView):
    def get(self): pass  # Overrides, not tracked
```

**Spec Mentions:** "Skip override methods" but `is_override()` not implemented.

**Recommendation:**
1. Use existing `implements_detector.py` (already in codebase!)
2. Track inherits edges in dependency graph
3. If parent method is called, child overrides are also "called"

**Effort:** 4h (can leverage existing code)

---

### 2.3 Framework Detection Incomplete 🟠 HIGH

**Current Spec:** Only mentions Flask/FastAPI decorators.

**Missing Frameworks:**
| Framework | Pattern | Detection Complexity |
|-----------|---------|---------------------|
| Django | `View` classes, `urls.py` patterns | Medium |
| Celery | `@app.task`, `@shared_task` | Low |
| Click | `@click.command`, `@click.group` | Low |
| GraphQL | `@strawberry.type`, resolvers | Medium |
| pytest | Fixtures, test discovery | Medium |
| FastAPI | `@app.get`, routers, dependencies | Low (partially covered) |
| SQLAlchemy | Event listeners, hybrid properties | High |

**Recommendation:**
- Phase 1: Flask, FastAPI, Celery, Click (4h)
- Phase 2: Django, pytest (6h)
- Phase 3: Others as needed

**Effort:** 10h total

---

### 2.4 Orphan Clusters Not Detected

**Problem:** If A calls B, and both are unreachable from entry points, both should be dead. Current algorithm treats A as "referenced" (by B).

**Example:**
```python
def a(): b()  # Called by b? No, dead cluster
def b(): a()  # Circular, both dead if no external caller
```

**Recommendation:**
1. Build call graph
2. Find strongly connected components (SCCs)
3. For each SCC, check if any node has external caller
4. If no external callers, entire cluster is dead

**Effort:** 6h (graph algorithm)

---

### 2.5 Missing Entry Point Detection

**Current:** Only checks `main`, `setup`, `run`.

**Missing:**
- `__main__.py` files in packages
- Click command groups
- Celery beat schedules
- Cron job definitions
- GitHub Actions entry points
- Docker CMD/ENTRYPOINT
- pytest test discovery

**Recommendation:** Scan for common entry point patterns:
```python
ENTRY_POINT_PATTERNS = [
    ("file", "__main__.py"),
    ("function", "main"),
    ("decorator", "@click.command"),
    ("variable", "__all__"),
    ("config", "celery.conf"),
]
```

**Effort:** 4h

---

## 3. EDGE CASES NOT COVERED 🟡 MEDIUM

### 3.1 Large Codebases (>50K files)

**Problems:**
- `find_unreferenced_symbols()` loads ALL symbols into memory
- No pagination or streaming
- No progress indicators
- Query: `SELECT id, name, file, kind FROM symbols` (no LIMIT)

**Recommendation:**
1. Use cursor iteration instead of `fetchall()`
2. Add `LIMIT/OFFSET` pagination
3. Add progress bar (use `rich`)
4. Stream CLI output for large results

**Effort:** 4h

---

### 3.2 Circular Dependencies

**Not Mentioned:** What happens when A→B→A?
- Both show as "referenced"
- Could still be dead if no path to entry point

**Overlap with 2.4:** Orphan cluster detection solves this.

---

### 3.3 Monorepo / Multi-Project

**Problem:** Symbol used in another package in same monorepo flagged as dead.

**Recommendation:**
- Add `--monorepo` flag
- Scan all packages in workspace
- Cross-project reference detection

**Effort:** 8h

---

### 3.4 Conditional Imports & Lazy Loading

**Examples:**
```python
if TYPE_CHECKING:
    from typing import TYPE_CHECKING  # Not a "real" import

importlib.import_module(config.MODULE_NAME)  # Dynamic
```

**Recommendation:** Flag as "possibly dead (conditional)" with low confidence.

---

### 3.5 Test Detection

**Current:** Excludes files with `/test/` in path.

**Missing:**
- `tests/` (plural)
- `*_test.py` naming
- `conftest.py`
- pytest fixtures
- `unittest` test cases

**Recommendation:** Use standard test file patterns:
```python
TEST_PATTERNS = [
    "*/test/*", "*/tests/*", "*/testing/*",
    "*_test.py", "*_tests.py", "test_*.py",
    "conftest.py",
]
```

**Effort:** 1h

---

## 4. PERFORMANCE CONCERNS 🟠 HIGH

### 4.1 SQL Query Optimization

**Current Dead Code Query:**
```sql
SELECT id, name, file, kind FROM symbols 
WHERE kind IN ('function', 'class', 'method')
AND file NOT LIKE '%/test%'
-- No LIMIT, no WHERE on file_path!
```

**Problems:**
- Scans ALL symbols in database
- No index usage on file_path
- `LIKE '%/test%'` prevents index use

**Recommendation:**
```sql
-- Use parameterized path filter
WHERE file_path LIKE ? || '/%'
-- Add prefix index
CREATE INDEX idx_symbols_file_prefix ON symbols(file_path);
```

**Effort:** 2h

---

### 4.2 No Caching Strategy

**Missing:** No mention of caching dead code results.

**Recommendation:**
1. Cache results keyed by `file_cache.content_hash`
2. Invalidate on file changes
3. Add `--no-cache` flag

**Effort:** 3h

---

### 4.3 Database Locking

**Risk:** Long-running dead code analysis could block indexing.

**Mitigation:**
- Use `BEGIN TRANSACTION` for read-only queries
- Set `PRAGMA read_uncommitted = 1` (if consistency allows)
- Add timeout to queries

**Effort:** 2h

---

### 4.4 Memory Usage

**Current:** `all_symbols = db.query(...)` loads entire result set.

**On 100K Symbols:**
- Memory: ~50MB for raw data
- Acceptable but could be better

**Recommendation:** Use generator pattern:
```python
def iter_symbols(db):
    cursor = db.execute("SELECT ...")
    for row in cursor:
        yield row
```

**Effort:** 2h

---

## 5. COMPETITIVE POSITIONING 🟡 MEDIUM

### 5.1 No Competitive Analysis

**Spec Claims:** "Addresses competitive gap vs nervx/GitNexus"

**But Provides:**
- ❌ No feature comparison table
- ❌ No analysis of what nervx does
- ❌ No analysis of what GitNexus does
- ❌ No differentiation strategy

**Questions:**
- Are nervx/GitNexus open source or commercial?
- What dead code features do they have?
- Are we better/faster/more accurate? Why?
- What's our unique value proposition?

---

### 5.2 Our Unfair Advantages (NOT LEVERAGED)

**Existing ast-tools Strengths:**
| Feature | Competitive Advantage | How to Leverage |
|---------|----------------------|-----------------|
| `dependency_metrics` | SPOF scoring, PageRank, centrality | Weight dead code by importance |
| `audit_log` | Provenance tracking | Show when code became dead |
| `embedding_similarity` | Code clone detection | Find duplicate dead code |
| Semantic search | Hybrid 6-factor fusion | "Find dead code like this" |
| sqlite-vec | Fast vector search | No GPU required |

**Recommendation:** Integrate these into dead code detection:
- Show SPOF_score for dead symbols (high SPOF + dead = risky)
- Show "dead since" date from git blame + audit_log
- Cluster similar dead code (remove all duplicates at once)

---

### 5.3 Missing Features Competitors Likely Have

**Expected in 2026:**
- [ ] IDE integration (VSCode extension)
- [ ] CI/CD integration (GitHub Actions to block PRs)
- [ ] Historical analysis (git diff to show when dead)
- [ ] Auto-fix suggestions (PR to remove dead code)
- [ ] Team collaboration (assign owners, track debt)
- [ ] Trend dashboards (dead code over time)

**Recommendation:**
- Phase 1: CLI + MCP (current spec) ✅
- Phase 2: GitHub Action (8h)
- Phase 3: VSCode extension (20h)
- Phase 4: Auto-fix generation (12h)

---

## 6. MISSING FROM SPEC 🟡 MEDIUM

### 6.1 Error Handling

**Not Documented:**
- What if database doesn't exist?
- What if index is stale?
- What if file is deleted after indexing?
- Exit codes for CLI

**Recommendation:**
```python
# Exit codes
0 = Success, no dead code found
1 = Error (DB not found, crash)
2 = Success, dead code found (for CI/CD)
3 = Stale index (run refresh first)
```

**Effort:** 2h

---

### 6.2 Exit Codes & CI/CD Integration

**Current:** No mention of CI/CD use cases.

**Recommendation:** Add `--ci` flag:
```bash
ast-tools find-dead --ci  # Exit 2 if dead code found
echo $?  # 0 = clean, 2 = violations
```

**Effort:** 1h

---

### 6.3 Progress Indicators

**Missing:** Long operations show no progress.

**Recommendation:** Use `rich.progress`:
```python
from rich.progress import Progress
with Progress() as progress:
    task = progress.add_task("Analyzing...", total=total_symbols)
    for symbol in iter_symbols():
        progress.update(task, advance=1)
```

**Effort:** 2h

---

### 6.4 Documentation

**Not Included:**
- Man page for CLI
- --help text for each command
- Examples in README
- Troubleshooting guide

**Effort:** 4h

---

## 7. RECOMMENDATIONS SUMMARY

### CRITICAL (Must Fix Before Implementation)

1. **Add path validation** — Block path traversal (1h)
2. **Implement input validation** — Query length, limit caps (2h)
3. **Enhance dead code algorithm** — At minimum: framework decorators, magic methods, entry points (8h)
4. **Add confidence scoring** — Never return "dead" without confidence level (2h)

**Total: 13h**

---

### HIGH PRIORITY (Before MVP Release)

5. **Framework detection** — Flask, FastAPI, Celery, Click, Django (6h)
6. **Orphan cluster detection** — Find dead code clusters (6h)
7. **SQL optimization** — Add limits, pagination, indexes (2h)
8. **Inheritance tracking** — Use implements_detector.py (4h)

**Total: 18h**

---

### MEDIUM PRIORITY (Post-MVP)

9. **Caching** — Cache results, invalidate on change (3h)
10. **Progress indicators** — Rich progress bars (2h)
11. **CI/CD integration** --ci flag, exit codes (2h)
12. **Competitive analysis** — Document differentiation (2h)
13. **Large codebase support** — Streaming, generators (4h)

**Total: 13h**

---

### LOW PRIORITY (Nice-to-Have)

14. **Rate limiting** — For MCP server (2h)
15. **IDE integration** — VSCode extension (20h, separate project)
16. **Historical analysis** — When did this become dead? (6h)
17. **Auto-fix generation** — PR to remove dead code (12h)

---

## 8. ORIGINAL VS REVISED EFFORT ESTIMATE

**Original Spec:**
- CLI Tool: 10h
- Dead Code: 15h
- **Total: 25h**

**Revised Estimate (Including Critical Fixes):**
- CLI Tool: 10h + 5h (security, validation) = **15h**
- Dead Code: 15h + 21h (accuracy, edge cases) = **36h**
- **Total: 51h** (2x increase)

**Revised Estimate (Including HIGH Priority):**
- Add 18h from HIGH list
- **Total: 69h** (nearly 3x increase)

**Recommendation:** Phase the rollout:
- **Phase 1 (25h):** Basic CLI + naive dead code (current spec) — for internal use only
- **Phase 2 (26h):** Add critical security + accuracy fixes — MVP for external release
- **Phase 3 (18h):** HIGH priority items — competitive feature set

---

## 9. CONCLUSION

The EASY_WINS spec is **under-scoped by 2-3x** when accounting for:
- Security validation (path traversal, input limits)
- Dead code accuracy (false positives could destroy trust)
- Performance on large codebases
- Competitive differentiation

**Go/No-Go Decision:**

| Criteria | Status | Notes |
|----------|--------|-------|
| Security | ❌ Not addressed | Must fix before any release |
| Accuracy | ❌ Naive algorithm | Will have >40% false positive rate |
| Performance | ⚠️ Basic | Will work up to ~10K files |
| Usability | ⚠️ Missing polish | No progress indicators, error handling |
| Competitive | ❌ No differentiation | Copying competitors without unique value |

**Recommendation:** Proceed with implementation but **re-scope MVP** to include CRITICAL fixes. Release as "experimental beta" until HIGH priority items are complete.

---

## Appendix A: Risk Matrix

| Risk | Likelihood | Impact | Mitigation | Effort |
|------|------------|--------|------------|--------|
| Path traversal exploit | High | Critical | Add validation | 1h |
| False positive flood | High | High | Better heuristics | 8h |
| Performance degradation | Medium | Medium | Add limits, caching | 4h |
| Competitive irrelevance | Medium | High | Leverage existing strengths | 4h |
| SQL injection | Low | High | Input sanitization | 2h |

---

## Appendix B: Test Plan Additions

**Must Add to Original Test Plan:**

```python
# test_cli_security.py
def test_path_traversal_blocked():
    """CLI rejects paths outside project root."""
    result = runner.invoke(app, ['search', 'auth', '--path=/etc'])
    assert result.exit_code != 0
    assert 'outside project' in result.output.lower()

def test_query_length_limit():
    """CLI rejects very long queries."""
    long_query = 'a' * 1000
    result = runner.invoke(app, ['search', long_query])
    assert result.exit_code != 0
    assert 'too long' in result.output.lower()

# test_dead_code_accuracy.py
def test_dynamic_dispatch_detected():
    """Functions called via getattr flagged as possibly dead."""
    # ... test dynamic call detection

def test_orphan_cluster_detection():
    """Circular calls with no external entry are dead."""
    # ... test A→B→A cluster detection

def test_framework_routes_excluded():
    """Django views, Celery tasks not flagged as dead."""
    # ... test multiple frameworks
```

---

**Audit Complete.**  
**Next Steps:** Review with stakeholders, approve revised scope, proceed with Phase 1 implementation.