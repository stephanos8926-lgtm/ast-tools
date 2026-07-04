# Testing Infrastructure Improvement Plan

> **Date:** 2026-07-04
> **Version:** v0.1.0
> **Status:** Draft
> **Author:** Lucien (RapidWebs Enterprise)

---

## 1. Current State Assessment

| Metric | Value | Notes |
|--------|-------|-------|
| Test files | 48 | Across 10 subdirectories + root |
| Total tests | 731 | 724 passing (99%), 7 fixed this session |
| Slowest dir | `tests/tools/` | ~50s+ total, embedding model loading |
| Other dirs | 0.5–16s each | Healthy, well-factored |
| Full suite (workstation) | Timeout at 90s+ | 4GB RAM ceiling — xdist causes OOM |
| Bottleneck | RAM, not CPU | Embedding model in memory |

### Key Bottlenecks

1. **No test tiering** — every run executes all 731 tests. No fast-path for pre-commit sanity.
2. **Model reload per file** — `test_semantic_search_context.py` loads sentence-transformers every run (14s).
3. **No timeouts per test** — a single wedged test blocks the entire suite.
4. **No CI optimizations** — GitHub Actions runs everything or nothing. No tiered jobs.
5. **No coverage enforcement** — `[tool.coverage]` is configured but never checked in CI.
6. **No performance regression tracking** — silently slowing tests go unnoticed.

---

## 2. Implementation Plan

### 🟢 Phase 1: Quick Wins (45 min)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 1.1 | Add `@pytest.mark.smoke/unit/integration/e2e` markers to all tests | 20 min | Enables `pytest -m smoke` in <5s |
| 1.2 | Install `pytest-timeout`, add global 60s timeout | 2 min | Prevents suite wedging |
| 1.3 | Add `just fastcheck` / Makefile alias for fast sanity | 5 min | `just fastcheck` = smoke + governance + CLI (~15s) |
| 1.4 | Update `pyproject.toml` with tier config | 3 min | DRY marker definitions |

### 🟡 Phase 2: Medium Impact (2–4 hours)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 2.1 | Session-scoped model fixture for embedding tests | 30 min | Drops `tools/` runtime 14s → ~2s |
| 2.2 | CI tiered execution (GitHub Actions) | 1 hr | Smoke run in <1 min on every push |
| 2.3 | Pre-indexed test database fixture | 1 hr | Drops indexer tests 16s → <1s |
| 2.4 | `pytest-cov` CI step with threshold | 30 min | Prevents coverage regressions |

### 🔵 Phase 3: Long-Term (1–2 days)

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 3.1 | Test duration regression benchmarks | 4 hr | Alerts on per-test perf regressions >20% |
| 3.2 | Randomized test ordering + isolation | 2 hr | Catches test pollution (order-dependent failures) |
| 3.3 | Fuzz testing for CLI commands | 3 hr | Edge cases + malformed input coverage |
| 3.4 | Property-based testing for DB queries | 4 hr | Hypothesis-based: "for all valid inputs, invariant holds" |
| 3.5 | Hermes plugin integration tests | 2 hr | End-to-end: plugin loads → session hooks fire → correct context injected |
| 3.6 | Cross-python-version matrix in CI | 2 hr | Test on 3.11, 3.12, 3.13, 3.14 |

---

## 3. Detailed Specifications

### 3.1 Test Tier Markers

**Marker definitions** (in `pyproject.toml`):

```toml
[tool.pytest.ini_options]
markers = [
    "smoke: quick smoke tests (pre-commit gate, <5s)",
    "unit: isolated unit tests, no external deps",
    "integration: tests requiring DB or file I/O",
    "e2e: full end-to-end workflows",
    "slow: tests that take >5s (excluded from default)",
]
```

**Tier assignment rules:**

| Marker | Criteria | Example tests | Max duration |
|--------|----------|---------------|-------------|
| `smoke` | CLI help, import checks, version strings | `test_cli.py::TestCLIHelp` | <5s |
| `unit` | Pure functions, isolated logic, no I/O | `test_rrf.py`, `test_schema.py` | <2s |
| `integration` | File/DB operations, index queries | `test_database/`, `test_indexer/` | <30s |
| `e2e` | Full workflows, subprocess invocations | `test_cli.py::TestCLIE2E` | <60s |

**Recommended tags per directory:**

| Directory | Primary marker | Notes |
|-----------|---------------|-------|
| `tests/test_cli.py` — Help/version | `smoke` | |
| `tests/test_cli.py` — Output formats | `smoke` | |
| `tests/test_cli.py` — E2E | `e2e` | |
| `tests/governance/` | `unit` | Pure logic |
| `tests/curator/` | `unit` | CLI + DB mocks |
| `tests/database/` | `integration` | Needs DB |
| `tests/indexer/` | `integration` | Needs DB |
| `tests/embeddings/` | `integration` | Needs model |
| `tests/kg/` | `unit` | Pure graph logic |
| `tests/cochange/` | `integration` | Needs git |
| `tests/context/` | `unit` | Pure logic |
| `tests/watcher/` | `integration` | Needs FS events |
| `tests/tools/test_rrf.py` | `unit` | Pure math |
| `tests/tools/test_dependency.py` | `integration` | Needs AST + files |
| `tests/tools/test_semantic_search_context.py` | `slow` | Model loading |

**Execution strategies:**

```bash
# Pre-commit (fast)
pytest -m "smoke" --no-header -q

# Pre-push (sanity)
pytest -m "smoke or unit" -n auto

# CI — smoke first (fail fast)
pytest -m "smoke" --no-header -q --tb=short
pytest -m "not smoke and not slow" --no-header -q  # parallel job
pytest -m "slow" --no-header -q  # separate job, model-only runs

# Full suite (nightly or pre-release)
pytest --tb=line -q
```

### 3.2 Session-Scoped Model Fixture

**Problem:** `tests/tools/test_semantic_search_context.py` calls `get_model()` on every file load, loading the sentence-transformers model from disk each time (14s total).

**Solution:** Create a shared conftest fixture at `tests/conftest.py`:

```python
import pytest
from ast_tools.embeddings.model import get_model

@pytest.fixture(scope="session")
def embedding_model():
    """Load embedding model once per session — shared across all test files."""
    model = get_model()
    return model
```

**Usage in test files:**

```python
class TestSemanticSearchContext:
    def test_inject_context(self, embedding_model):
        # embedding_model is pre-loaded — no per-test cost
        ...
```

**Expected improvement:** 14s → ~2s (first load still happens, but cached for all subsequent tests).

**Caveat:** The model takes ~600MB RAM. With session scope, it stays in memory for the entire pytest session. On a 4GB machine, this means it's loaded for ALL tests, not just the ones that need it. Consider marking these tests with `@pytest.mark.slow` and excluding them from CI smoke runs.

### 3.3 CI Tiered Execution

**GitHub Actions workflow** (`.github/workflows/ci.yml`):

```yaml
name: CI

on: [push, pull_request]

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install uv && uv sync --group dev
      - run: uv run pytest -m "smoke" --tb=short -q
      # Expected: <30s

  unit-and-integration:
    needs: smoke
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install uv && uv sync --group dev
      - run: uv run pytest -m "not smoke and not slow" --tb=short -q
      # Expected: <2 min

  slow:
    needs: smoke
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install uv && uv sync --group dev
      - run: uv run pytest -m "slow" --tb=short -q
      # Expected: <30s (model loading)

  coverage:
    needs: [smoke, unit-and-integration]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install uv && uv sync --group dev
      - run: uv run pytest -m "not slow" --cov=ast_tools --cov-report=xml
      - run: uv run python -m coverage report --fail-under=80
```

### 3.4 Pre-Indexed Database Fixture

**Problem:** Tests in `tests/indexer/` and `tests/database/` create fresh projects, index them from scratch, then run queries. This takes 16s for indexer tests alone.

**Solution:** Check in a pre-built test database under `tests/fixtures/test_index.db` with a known set of symbols. Tests can copy it to a temp location and query against it instantly.

```python
# tests/conftest.py
import shutil
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TEST_DB = FIXTURE_DIR / "test_index.db"

@pytest.fixture(scope="session")
def db_path():
    """Copy pre-built test DB to temp dir — 100x faster than building from scratch."""
    import tempfile
    dst = Path(tempfile.mkdtemp()) / "index.db"
    shutil.copy2(TEST_DB, dst)
    return dst
```

**How to build the fixture DB:**

```bash
# One-time build:
cd ast-tools && uv run python -c "
from ast_tools.indexer.extractor import extract_all
from ast_tools.database.connection import get_db_path, init_db
from ast_tools.database import database_context
from ast_tools.embeddings.model import get_model

db = get_db_path()
init_db(db)
extract_all(['src/ast_tools'], db)
# Copy to fixtures
import shutil; shutil.copy2(db, 'tests/fixtures/test_index.db')
"
```

**Expected improvement:** 16s → <0.5s.

### 3.5 Test Duration Regression Benchmarks

**Tool:** `pytest-benchmark` or custom `--durations` tracking.

**Implementation:**

```python
# tests/conftest.py (optional benchmark integration)
def pytest_benchmark_update_machine_info(config, machine_info):
    machine_info['commit'] = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD']
    ).decode().strip()
```

**CI check:**

```yaml
- name: Check test duration regression
  run: |
    uv run pytest --durations=20 -q | tee durations.txt
    # Compare durations.txt against benchmark baseline
    # Fail if any test regressed >20%
```

**Baseline capture:** Run once after tagging and commit the `--durations` output. Compare on subsequent CI runs.

### 3.6 Fuzz Testing for CLI

**Tool:** Hypothesis (property-based testing).

```python
from hypothesis import given, strategies as st
from ast_tools.cli import cmd_browse

@given(kind=st.sampled_from(["function", "class", "method", "variable", "all"]))
def test_browse_never_crashes(kind):
    """Browse handles all valid kind values without crashing."""
    ...
```

**Coverage targets:** CLI argument parsing, file path handling, format output (table/JSON/markdown).

### 3.7 Hermes Plugin Integration Tests

End-to-end tests that verify the 3 Hermes plugins (`ast-tools-context`, `ast-tools-tokens`, `ast-tools-project-context`) actually:

1. Load without errors in a Hermes session
2. Fire hooks on the correct events
3. Inject context with correct structure
4. Handle missing/token-budget scenarios

**Requires:** A Hermes test harness or mock `HermesSession`.

### 3.8 Cross-Python-Version Matrix

```yaml
strategy:
  matrix:
    python-version: ["3.11", "3.12", "3.13", "3.14"]
```

**Note:** Our `pyproject.toml` declares `requires-python = ">=3.10"`. Adding 3.14 (currently the workstation's Python) catches version-specific issues early.

---

## 4. Impact Analysis

| Phase | Total reduction | Confidence | Risk |
|-------|----------------|------------|------|
| Phase 1 (Quick Wins) | Smoke pass: 731→~25 tests | High | None |
| Phase 2 (Medium) | Full suite: ~120s → ~45s | High | DB fixture staleness |
| Phase 3 (Long) | N/A (quality, not speed) | Medium | Model fixture RAM pressure |

### Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Pre-indexed DB becomes stale (schema changes) | Medium | CI rebuilds fixture DB on schema version change |
| Model fixture OOM on 4GB | Medium | Mark `slow` tests, exclude from smoke/default runs |
| Marker misclassification | Low | Code review on marker PR; adjust after first week |
| `pytest-timeout` kills legitimate slow tests | Low | Set generous per-test timeout (60s) with exceptions for `slow` marked tests |

---

## 5. Recommendations

### Do First (Phase 1 — Quick Wins)
Test tiers + `pytest-timeout` + pre-commit alias. These cost almost nothing, have no risk, and immediately improve the development loop.

### Do Next (Phase 2 — Medium)
Model fixture + CI tiering. These address the real pain points: slow embedding tests and CI that runs everything.

### Do When You Have Time (Phase 3)
Pre-indexed DB fixture + regression benchmarks + fuzzing. These are quality-of-life improvements that compound over time.