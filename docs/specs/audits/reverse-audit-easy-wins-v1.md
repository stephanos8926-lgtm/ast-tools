# Reverse Audit: Easy Wins Implementation Plan (CLI + Dead Code)

**Date:** 2026-06-28  
**Auditor:** Subagent (deleg_51ea1d37)  
**Mode:** MEDIUM (plan-and-audit)  
**Scope:** Find EVERYTHING the plan MISSES

---

## Audit Goals

1. Find dead code (never-imported modules)
2. Find stale test files
3. Check .gitignore gaps
4. Find duplicate functionality
5. Check for broken imports
6. Search for secrets/credentials in repo
7. Identify oversized files (>500 lines)
8. Check for missing `__init__.py`
9. **Path traversal risks** — tools accepting file_path without validation
10. **Test/code contract drift** — verify error keys match
11. **Subprocess safety** — check for shell=True, string args
12. **Error information leakage**

---

## Checklist

### Security & Safety

- [ ] CLI input validation (argparse handles edge cases?)
- [ ] Path traversal check in CLI commands (is_relative_to() used?)
- [ ] Dead code detection doesn't expose sensitive files
- [ ] No secrets in repo (API keys, credentials)
- [ ] No shell=True in new code

### Edge Cases

- [ ] Large codebases (>100K files) — performance concerns?
- [ ] Circular dependencies — will dead code detection infinite loop?
- [ ] Polymorphism — can we detect abstract method implementations?
- [ ] Dynamic dispatch — `getattr()`, `__call__` — dead code might miss these
- [ ] Test files with unusual naming patterns

### False Positive Scenarios (Dead Code)

- [ ] Entry points in non-standard locations
- [ ] Framework conventions (Click commands, Celery tasks, Alembic migrations)
- [ ] Plugin systems (dynamically loaded modules)
- [ ] Vendored code
- [ ] Generated code

### Performance

- [ ] SQL query efficiency for unreferenced symbols query
- [ ] Caching strategy for repeated dead code scans
- [ ] Memory usage for large codebases

---

## Findings by Severity

### 🔴 Critical

1. **Path traversal vulnerability** — CLI `--path` accepts any directory with no validation
2. **Dead code false positives >40%** — Missing polymorphism, dynamic dispatch, framework detection

### 🟠 High

1. **Dynamic dispatch not tracked** — `getattr()`, `importlib` calls create false positives
2. **Polymorphism & inheritance** — `is_override()` not implemented
3. **Framework detection incomplete** — Only Flask/FastAPI, missing Django/Celery/Click/pytest
4. **SQL query optimization needed** — No limits, poor index usage, `LIKE '%/test%'` anti-pattern

### 🟡 Medium

1. **Large codebases (>50K files)** — No pagination, streaming, or progress indicators
2. **Orphan clusters** — Circular dead code not detected (A→B→A with no entry point)
3. **No caching** — Results not cached between runs
4. **Missing competitive analysis** — No comparison to nervx/GitNexus features
5. **Entry point detection incomplete** — Only checks `main`/`setup`/`run`
6. **Test file patterns incomplete** — Misses `tests/`, `*_test.py`, `conftest.py`

### 🔵 Low

1. **No CI/CD integration** — `--ci` flag for exit codes
2. **No progress indicators** — Long operations show no feedback
3. **Exit codes not documented** — What does exit 0 vs 2 mean?

### 📋 Full List

See `docs/EASY_WINS_REVERSE_AUDIT.md` for complete findings (651 lines, 17KB)

---

## Recommendations

1. ...
2. ...

---

*Template ready for auditor to fill in.*