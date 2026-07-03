# Reverse Audit: All 7 Planning Documents — Gaps & Risks

**Audit Date:** 2026-07-02  
**Auditor:** Lucien (Lead Digital Architect)  
**Documents Audited:**
1. `docs/adrs/0009-reranker-integration.md` — Reranker plan
2. `docs/adrs/0010-architecture-governance-engine.md` — Governance engine
3. `docs/adrs/0011-pypi-name-decision-and-publishing-pipeline.md` — PyPI publishing
4. `docs/specs/TOOLING_SPEC.md` — Master spec (Categories A–D)
5. `docs/specs/category-c-autofix-and-reporter.md` — Autofix + report
6. `docs/plans/category-deployment-launch.md` — Launch plan
7. `docs/plans/phase7-performance-optimization.md` — Performance opt

**Actual Project State (verified):**
- 53 tools registered, 17 CLI subcommands in `cli.py` (argparse)
- No `governance/`, `fix/`, `reranker/`, `dashboard/` directories exist
- `pyproject.toml` already at `name = "ast-tools-mcp"` v0.1.0
- CI/CD exists: `release.yaml`, `ci.yaml`, `security-audit.yaml`
- Existing import graph infrastructure in `dependencies.graph`, `module_imports.py`, `tools/impact_analysis.py`

---

## Severity Legend

| Marker | Severity | Description |
|--------|----------|-------------|
| 🔴 | **Critical** | Would block the feature, break existing functionality, or cause data loss |
| 🟠 | **High** | Significant missing scope, integration issues, or deployment blockers |
| 🟡 | **Medium** | Missing edge cases, documentation gaps, or suboptimal design choices |
| 🟢 | **Low** | Nice-to-haves, polish items, or minor omissions |

---

## 🔴 Critical Gaps

### C1. No DB Schema Migration or Rollback Strategy

**Source:** ADR-0010, category-c autofix spec, phase7 plan  
**Documents:** 2, 4, 5, 7  
**Severity:** 🔴

**What's missing:** Three of the seven documents introduce changes that touch the SQLite database or index schema, yet **zero** documents mention schema versioning, migration scripts, or rollback procedures.

- ADR-0010's scanner layer imports the existing import graph but doesn't specify whether it writes new tables or reads existing ones.
- Spec cat-c part 2 (architecture dashboard) reads from "the project's SQLite database" without specifying schema expectations.
- Phase7 Task 2 checks for `schema_version` when doing incremental indexing but none of the new features define their schema version requirements.

**Risk:** A production deploy that adds governance tables or changes the index schema will break all existing installations. Rollback requires a database rebuild with no documented procedure.

**Recommendation:** Define a `schema_version` in the database, create migration scripts (`migrations/001_*.sql`, `migrations/002_*.sql`), and implement `alembic`-style upgrade/downgrade for any DB changes.

---

### C2. Governance CLI Conflicts with Existing CLI Architecture

**Source:** ADR-0010  
**Document:** 2  
**Severity:** 🔴

**What's missing:** ADR-0010 proposes `ast governance init/check/diff/report/baseline` as a subcommand group. The existing `cli.py` uses `argparse` with **17 flat subcommands** (`search`, `navigate`, `blast-radius`, `find-dead`, `summary`, `symbols`, `refs`, `callers`, `callees`, `deps`, `browse`, `init`, `doctor`, `vacuum`, `curator`, `cleanup`, `config`).

**Risk:** No analysis of:
- How `governance` gets added as a nested subcommand without breaking existing argparse structure
- Whether `init` conflicts (existing `ast init` runs the setup wizard, governance wants `ast governance init`)
- Whether `report` conflicts (no existing report command, but no namespace analysis either)
- The governance CLI file is placed at `cli.py` (top-level) per ADR-0010 file structure, but the existing `cli.py` already exists with different semantics

**Recommendation:** Create a CLI integration plan that either (a) adds `governance` as a sub-subparser on the existing `cli.py`, (b) uses Click-style command groups if migrating, or (c) delegates to `ast_tools/governance/cli.py` via a dispatch pattern. Document exactly how `ast governance` avoids name collision.

---

### C3. Reranker Model Download: No Failure Mode Handling

**Source:** ADR-0009  
**Document:** 1  
**Severity:** 🔴

**What's missing:** ADR-0009 describes "automatic model downloading" via HuggingFace Hub for the CrossEncoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2`, ~80MB). The document covers **zero** failure modes:

| Scenario | Missing |
|----------|---------|
| No internet / offline environment | No fallback to bundled model or graceful degradation |
| Corporate proxy blocking HuggingFace | No proxy config support |
| HuggingFace API rate limits | No retry/backoff |
| Disk full during download | No space check before download |
| Download interrupted mid-way | No resume/corrupt-file detection |
| HuggingFace token required for gated models | No token configuration point |
| Model version changes on HF (new commit) | No model version pinning |
| Model deleted from HF Hub | No fallback model alternative |

**Risk:** `semantic_search(query, use_reranker=True)` silently hangs or throws an opaque exception in common network-restricted environments (CI, enterprise firewalls, air-gapped servers).

**Recommendation:** Define:
1. A `HF_HUB_CACHE` or configurable model cache path
2. Download timeout + retry with exponential backoff
3. Offline detection: emit clear error if no network and model not cached
4. Model version pinning via revision hash
5. Graceful fallback: `use_reranker=True` falls back to RRF-only if model unavailable

---

### C4. No Backward Compatibility Path for Old PyPI Name

**Source:** ADR-0011  
**Document:** 3  
**Severity:** 🔴

**What's missing:** The name changes from `ast-tools` to `ast-tools-mcp` on PyPI. Existing users who installed via `pip install ast-tools` will **not** get updates, and there is **zero** mechanism to bridge them:

- No shim/alias package `ast-tools` → `ast-tools-mcp` published on PyPI
- No deprecation warning in the old `ast-tools` v0.1.8 (it's an unrelated package — we can't control it)
- No migration instructions for users who have the old name in `requirements.txt`/`pyproject.toml`
- No redirect or forwarding mechanism (PyPI doesn't support package aliases)

**Risk:** Users pinning `ast-tools>=0.2.0` will get the *wrong* package (the unrelated v0.1.8 toolbox). Users who search PyPI for "ast-tools" will find the old abandoned package, not the new one.

**Recommendation:** 
1. Create a minimal `ast-tools` shim package on PyPI that imports and re-exports `ast_tools_mcp` with a deprecation warning
2. Document the migration path prominently in README
3. Submit a takedown request for PyPI project name squatting (the old package is unrelated and abandoned)
4. Add `pip install ast-tools-mcp` as the install command everywhere

---

### C5. CI/CD Points to Wrong PyPI URL

**Source:** ADR-0011, release.yaml  
**Document:** 3, actual project state  
**Severity:** 🔴

**What's missing:** `.github/workflows/release.yaml` line 18:
```yaml
url: https://pypi.org/p/ast-tools
```

But the actual package name is now `ast-tools-mcp`. The PyPI environment URL still references the old name.

**Risk:** The GitHub Actions environment trust-publishing will fail or publish to the wrong project. The OIDC identity provider binding will not match.

**Recommendation:** Update to `url: https://pypi.org/p/ast-tools-mcp`.

---

### C6. Zero Tests Exist for Any Planned Feature

**Source:** All documents  
**Documents:** 1, 2, 4, 5, 6, 7  
**Severity:** 🔴

**What's missing:** Every document describes test plans in detail, but **zero test files exist** in the source tree for any new feature:

| Feature | Tests mentioned in doc | Actual file in repo |
|---------|----------------------|-------------------|
| Reranker | `tests/test_reranker.py` | ❌ Does not exist |
| Governance engine | `tests/test_governance.py` | ❌ Does not exist |
| Auto-fix pipeline | `tests/test_fix.py` | ❌ Does not exist |
| Architecture dashboard | `tests/dashboard/` | ❌ Does not exist |
| PyPI publish verification | Manual test | ❌ No script exists |

**Risk:** Features will be developed without test coverage, directly contradicting the project's TDD principles. Regressions impossible to catch.

**Recommendation:** Implement TDD tests **before** feature code, per the project's established practice.

---

### C7. No Server Sync / Deployment Strategy

**Source:** Master spec Category A  
**Document:** 4  
**Severity:** 🔴

**What's missing:** The master spec mentions:
- "Fix the broken server virtual environment"
- "Ensure seamless synchronization of source files"
- "rsync or equivalent for server synchronization"

But none of the 7 documents detail:
- How `ast-tools` gets deployed to a server
- What server architecture is targeted
- How MCP server processes are managed (systemd? supervisor? docker?)
- How config/data dirs are synced between workstation and server
- How database files transfer between environments
- How secrets (PyPI token, HF token) are managed in production
- Zero doc on the server environment at all

**Risk:** On launch day, there is no documented way to deploy ast-tools to a server. The deployment plan is hand-waved as "rsync."

**Recommendation:** Create a deployment spec covering: target architecture, process supervision, data persistence, secret management, and a documented `scripts/deploy.sh`.

---

### C8. Multi-Arch Build: No CI Matrix for aarch64

**Source:** Launch plan D4  
**Document:** 6  
**Severity:** 🔴

**What's missing:** D4 targets "x86_64 and aarch64 (Linux)" and mentions "CI/CD pipelines successfully build for both." The actual `.github/workflows/ci.yaml` only has `runs-on: ubuntu-latest` (x86_64).

**Risk:** No aarch64 builder exists. `sentence-transformers` compatibility on ARM is speculated (line 47: "ensure sentence-transformers functions correctly on ARM") but never verified.

**Recommendation:** Add `runs-on: [self-hosted, linux, ARM64]` or use `docker/setup-qemu-action@v3` for emulated ARM builds. Test sentence-transformers on ARM explicitly.

---

## 🟠 High Gaps

### H1. Governance Scanner Duplicates Existing Import Graph

**Source:** ADR-0010  
**Document:** 2  
**Severity:** 🟠

**What's missing:** ADR-0010 Layer 2 defines `_build_import_graph(codebase_path)` as an internal helper of the scanner. But `ast-tools` **already has**:
- `src/ast_tools/dependencies/graph.py` — import graph built in Phase 10A
- `src/ast_tools/tools/module_imports.py` — per-file import analysis
- `tools/impact_analysis.py` — already wired to live graph

**Risk:** Two parallel import graph implementations will diverge. The governance scanner may miss imports the existing tooling catches, or produce different results.

**Recommendation:** Make the governance scanner depend on the existing `_build_import_graph()` or `dependencies.graph` infrastructure. Do not reimplement.

---

### H2. Autofix Pipeline: No Handling for Missing External Tools

**Source:** Spec cat-c, autofix spec  
**Documents:** 4, 5  
**Severity:** 🟠

**What's missing:** The `ast fix` command assumes `ruff`, `black`/`ruff format`, `prettier`, `eslint --fix`, `gofmt` are installed. There is **zero** handling for:
- External tool not found on PATH
- External tool not installed at all
- External tool version mismatch
- CI environment without Node.js (no prettier/eslint)

**Risk:** `ast fix` crashes with `FileNotFoundError` in common environments. Users get a broken experience on first use.

**Recommendation:** 
1. Check availability of each external tool before calling it
2. Emit clear actionable error: "ruff not found. Install with: pip install ruff"
3. Allow users to configure which fixers to use via config file
4. Gracefully skip unavailable fixers with a warning

---

### H3. Repository Scanner / Architecture Report Governance.yaml Ambiguity

**Source:** Spec cat-c part 2  
**Document:** 5  
**Severity:** 🟠

**What's missing:** Line 117:
> "If `governance.yaml` is not found or invalid, the tool should report an error or attempt to proceed with only the current architecture graph."

"Should report an error **or** attempt to proceed" is ambiguous. It's not clear which behavior is expected. This affects:
- Error exit codes for CI integration
- Whether the report is usable without governance rules
- Whether partial output is valid

**Recommendation:** Define exact behavior: report error with code 1 if governance.yaml not found (with `--no-governance` flag to force proceed). Do not leave it ambiguous.

---

### H4. Reranker Optional Dependency — Not Actually Optional

**Source:** ADR-0009, pyproject.toml  
**Documents:** 1, actual project state  
**Severity:** 🟠

**What's missing:** ADR-0009 describes the reranker as an "optional dependency" and says "Not strictly required for `ast-tools` to function." But `sentence-transformers` is listed in `[project.dependencies]` (not optional-dependencies) in `pyproject.toml`.

This means:
- Every user downloads sentence-transformers (~1GB+) regardless of whether they use the reranker
- The cold-start penalty (10-15s) affects ALL users, not just reranker users
- No `[project.optional-dependencies]` group exists for "reranker" or "ml" deps

**Risk:** The very first `import ast_tools` triggers a 10-15s SentenceTransformer load for ALL users, defeating the purpose of the Phase7 lazy loading optimization.

**Recommendation:** Move `sentence-transformers` to an optional dependency group `[project.optional-dependencies] reranker = ["sentence-transformers>=2.2.0"]`. Document that `pip install ast-tools-mcp[reranker]` is required for the reranker.

---

### H5. Release Workflow Missing CI Checks

**Source:** launch plan D3, release.yaml  
**Document:** 6, actual project state  
**Severity:** 🟠

**What's missing:** The release workflow triggers on tag push, but has no:
- Pre-publish validation step (tests don't run — that's only in CI)
- Version consistency check (tag version vs pyproject.toml version)
- CHANGELOG enforcement
- Dry-run publish step
- License/security audit gate

**Risk:** A tag push on a broken commit publishes a broken package. No validation exists between the push and the PyPI upload.

**Recommendation:** Add `needs: [ci/lint, ci/test, ci/security-audit]` or re-run tests in the release workflow. Add a version-consistency check step.

---

### H6. Reranker + Token Budget Interaction Unspecified

**Source:** ADR-0009, phase7 task6  
**Documents:** 1, 7  
**Severity:** 🟠

**What's missing:** The reranker produces top-5 results. Phase7 task6 enforces a token budget on `semantic_search` output. The interaction is undocumented:
- Does the token budget apply before or after reranking?
- If token budget truncates to 4096 tokens and reranker returns 5 results that exceed it, which ones get cut?
- Is the `truncated` flag (phase7) aware of reranking?

**Risk:** Users enabling both `use_reranker=True` and a tight `token_budget` get confusing results — top-ranked by reranker but truncated by token policy.

**Recommendation:** Define ordering: token budget is enforced on the reranker output, not the pre-reranker RRF output. Document in both specs.

---

### H7. No Dependency Pinning or Lockfile for Publishing

**Source:** ADR-0011 publish pipeline, launch plan D3  
**Documents:** 3, 6  
**Severity:** 🟠

**What's missing:** The publish pipeline runs `uv build` using whatever `pyproject.toml` specifies. There's no:
- `uv.lock` committed to the repo
- Dependency pinning in `pyproject.toml` (all deps use `>=` not `==`)
- SBOM generation
- `pip-audit` or vulnerability scan before publish

**Risk:** A transitive dependency release with a vulnerability or breaking change gets published as part of ast-tools without detection. No reproducible builds.

**Recommendation:** Commit `uv.lock`, add `pip-audit` to CI, and pin at least major.minor versions for core deps (`mcp`, `sentence-transformers`, `tree-sitter`).

---

### H8. No Test Fixture Isolation for Parallel Tests

**Source:** Phase7 task5  
**Document:** 7  
**Severity:** 🟠

**What's missing:** Phase7 adds `pytest-xdist` with `-n auto --dist worksteal` but the governance tests (ADR-0010) and autofix tests (cat-c spec) will share database state. No document mentions:
- How to isolate test databases per worker
- How to avoid temp-file collisions
- What happens when two workers try to write to the same SQLite DB

**Risk:** Flaky tests in CI due to `database is locked` errors. Tests pass locally but fail on parallel CI runners.

**Recommendation:** Use `tmp_path` fixtures for per-test database files. Set SQLite journal mode to WAL. Add `--randomly-dont-reorganize` or thread-safe temp dirs.

---

## 🟡 Medium Gaps

### M1. Governance Diff Duplicates Existing Co-Change Analysis

**Source:** ADR-0010  
**Document:** 2  
**Severity:** 🟡

**What's missing:** ADR-0010 proposes `ast governance diff` to compare architectural states between commits. `ast-tools` already has `cochange/git_miner.py` with git history analysis. No document mentions reusing that infrastructure.

**Recommendation:** Leverage `git_miner.py` for commit-level diffing instead of reimplementing git analysis.

---

### M2. Architecture Dashboard Data Source Confusion

**Source:** Spec cat-c part 2  
**Document:** 5  
**Severity:** 🟡

**What's missing:** The dashboard reads "current import graph from the project's SQLite database." But the governance engine (ADR-0010) builds its import graph by reading the codebase directly via AST traversal. These are two different graph representations that may not match.

No document specifies:
- Which DB tables hold the import graph
- How often the DB graph is refreshed vs the live AST graph
- What happens when the DB is stale

**Recommendation:** Single-source the import graph through the existing `dependencies.graph` module. The dashboard and governance scanner should both read from the same representation.

---

### M3. No Error Handling in publish.sh for Partial Failure

**Source:** ADR-0011, scripts/publish.sh  
**Document:** 3, actual project state  
**Severity:** 🟡

**What's missing:** `publish.sh` uses `set -e` which aborts on first error. But if `uv build` succeeds and `uv publish` fails, the dist/ directory contains orphaned build artifacts with no cleanup.

**Recommendation:** Add a trap handler: `trap 'rm -rf dist/' ERR` or document manual cleanup.

---

### M4. Reranker Timeout Value Not Defined

**Source:** ADR-0009  
**Document:** 1  
**Severity:** 🟡

**What's missing:** The test plan mentions "timeout handling" and the class diagram shows timeouts, but no actual timeout value or behavior is defined. How long should a single reranker prediction wait? What happens on timeout — partial rerank? All-RRF fallback? Exception?

**Recommendation:** Define a default timeout (e.g., 30s for the full reranking pass), with a configuration option. On timeout, log warning and use pre-reranker RRF results.

---

### M5. Token Budget Enforced But Not User-Configurable

**Source:** Phase7 task6  
**Document:** 7  
**Severity:** 🟡

**What's missing:** Task 6 adds a `truncated` flag and `total_tokens` to `semantic_search` response, and verifies `token_budget` is enforced. But there's no user-facing way to configure the budget (CLI arg, config file, env var).

**Recommendation:** Add `--token-budget` to `ast search` CLI and a `token_budget` config key.

---

### M6. Category A (Ship & Polish) Acceptance Criteria Underspecified

**Source:** Master spec  
**Document:** 4  
**Severity:** 🟡

**What's missing:** Category A acceptance criteria:
- "Benchmark results (time, token, latency) for indexing the Linux kernel are documented"
- No mention of what benchmark tool, what metrics, or what format

**Recommendation:** Reference the existing `benchmarks/phase9_benchmark.py`.

---

### M7. Publish Pipeline Mentions CHANGELOG but No Strategy

**Source:** Launch plan D3  
**Document:** 6  
**Severity:** 🟡

**What's missing:** D3 says "Create a GitHub release with the associated changelog" but there's no:
- CHANGELOG.md update step in the pipeline
- Changelog format defined (keep-a-changelog? auto-generated?)
- No step to ensure CHANGELOG is up to date before tagging

**Recommendation:** Add `./scripts/update-changelog.sh` or validate CHANGELOG freshness in CI.

---

## 🟢 Low Gaps

### L1. No CI Caching for Model Downloads

**Source:** ADR-0009, ci.yaml  
**Documents:** 1, actual project state  
**Severity:** 🟢

**Recommendation:** Add `actions/cache` for `~/.cache/huggingface/` in CI to avoid 80MB download on every test run.

---

### L2. Reranker search() Signature Change Extends but Doesn't Deprecate

**Source:** ADR-0009  
**Document:** 1  
**Severity:** 🟢

The `use_reranker` parameter defaults to `False`, so existing callers are unaffected. No deprecation policy needed.

---

### L3. No Telemetry or Usage Analytics in Publish

**Document:** 3, 6  
**Severity:** 🟢

No analytics is appropriate for an OSS tool. No action needed.

---

### L4. No Adapter Tests for Ast-Grep Bridge

**Source:** Launch plan D2  
**Document:** 6  
**Severity:** 🟢

D2 says "Unit tests for `ast_grep_bridge.py` should pass" but doesn't specify test cases (what happens when ast-grep isn't installed? what commands to test?).

**Recommendation:** Add at least 3 test cases: (1) ast-grep not installed → clear error, (2) valid translation, (3) unknown command → error.

---

### L5. No Dockerfile Multi-Stage Build

**Source:** Launch plan D4  
**Document:** 6  
**Severity:** 🟢

D4 mentions "Dockerfile (ensure multi-arch support)" but doesn't specify multi-stage builds for smaller image size.

**Recommendation:** Use multi-stage: build stage with all tooling, runtime stage with only needed deps.

---

## Cross-Feature Conflict Matrix

| Feature A | Feature B | Conflict | Doc |
|-----------|-----------|----------|-----|
| Governance scanner (`_build_import_graph`) | Existing `dependencies.graph` | Duplicate import graph implementation | ADR-0010 |
| Governance CLI `ast governance init` | Existing `ast init` (setup wizard) | Name collision (both use `init` subcommand) | ADR-0010 |
| Reranker (use_reranker param) | Token budget enforcement (phase7) | Ordering of truncation vs reranking undefined | ADR-0009, Phase7 |
| Parallel tests (pytest-xdist) | Governance/DB tests | Shared SQLite file → lock contention | ADR-0010, Phase7 |
| Architecture dashboard (SQLite graph) | Governance scanner (live AST graph) | Two different import graphs | Cat-c spec, ADR-0010 |

---

## Dependency Chain Issues

| Issue | Impact | Documents |
|-------|--------|-----------|
| sentence-transformers in `[dependencies]` is **not** optional | All users pay 1GB+ download + 10-15s cold start | ADR-0009, pyproject.toml |
| CrossEncoder model = 80MB disk with no cache management | Fills disk on repeated CI runs | ADR-0009 |
| aarch64 CI not configured | Multi-arch builds will fail silently | Launch plan D4 |
| `release.yaml` points to wrong PyPI URL | Publish to `ast-tools` instead of `ast-tools-mcp` | release.yaml |
| No `uv.lock` in repo | Non-reproducible builds | ADR-0011 |
| `ast-tools` PyPI name not reclaimed | Users find wrong package | ADR-0011 |

---

## Summary Statistics

| Severity | Count | Key Examples |
|----------|-------|-------------|
| 🔴 Critical | 8 | No DB migration, CLI conflict, no download failure handling, no backward compat, wrong CI URL, zero tests, no deploy strategy, no ARM CI |
| 🟠 High | 8 | Duplicate import graph, missing external tool handling, ambiguous fallback, false optional dep, no pre-publish CI, token budget interaction, no lockfile, test isolation |
| 🟡 Medium | 7 | Dead code detector collision, dashboard data source confusion, publish.sh partial failure, undefined timeout, non-configurable token budget, underspecified acceptance criteria, no CHANGELOG strategy |
| 🟢 Low | 5 | No CI caching, trivial items, no adapter tests, no multi-stage Dockerfile |

**Total: 28 gaps identified across 7 documents.**

---

## Immediate Action Items (must-fix before any implementation)

1. ✅ Update `release.yaml` PyPI URL to `ast-tools-mcp`
2. ✅ Move `sentence-transformers` to `[project.optional-dependencies]`
3. ✅ Define DB schema migration strategy for any feature touching the SQLite database
4. ✅ Fix `release.yaml` environment URL (C5)
5. ✅ Write CLI integration plan for `ast governance` subcommands (C2)
6. ✅ Add model download failure handling spec (C3)
7. ✅ Plan backward compatibility for old PyPI users (C4)
8. ✅ Commit `uv.lock` for reproducible builds (H7)
9. ✅ Add aarch64 CI matrix (C8)
10. ✅ Create server deployment spec (C7)
