## Master Spec: All Remaining ast-tools Features

**Current State:** 55 tools, 330+ tests, Phases 0-10 completed. 693 tests collected.

---

### Category A — Ship & Polish (1-2 days)

*   **Goal:** Get ast-tools ready for public release.

*   **Problem Statement:** The existing PyPI name "ast-tools" is taken, preventing a direct release. Additionally, critical bugs in the server environment and core functionalities need to be fixed to ensure a stable and professional first release. Documentation and release processes also require updates for an open-source audience.

*   **Proposed Solution:**
    1.  Address the PyPI name conflict by selecting and implementing a new package name.
    2.  Rectify the broken server virtual environment and ensure seamless synchronization of source files.
    3.  Update all relevant project files (`pyproject.toml`, documentation, README) to reflect the new name.
    4.  Conduct a performance benchmark to establish baseline metrics.
    5.  Implement CI/CD for automated publishing to PyPI.
    6.  Revise the README for an OSS audience, focusing on onboarding and use cases beyond internal development.

*   **Components List:**
    *   Name selection utility/process.
    *   Virtual environment repair scripts/instructions.
    *   `rsync` or equivalent for server synchronization.
    *   `pyproject.toml` modification tooling.
    *   Documentation update scripts/manual process.
    *   Benchmarking tool integration.
    *   GitHub Actions for PyPI publishing.
    *   README content generation.

*   **Files to Create/Modify:**
    *   `pyproject.toml` (package name, metadata)
    *   `README.md` (rewrite for OSS)
    *   `docs/` directory (update references to package name)
    *   `.github/workflows/publish.yml` (new CI/CD for PyPI)
    *   Server-side environment setup scripts (for fixing venv).
    *   Potentially utility scripts for automated renaming if feasible.

*   **Dependencies Between Categories:**
    *   Category A must be completed before Category D can begin, as A focuses on release readiness and D is about launch preparation.

*   **Acceptance Criteria:**
    *   A new, available PyPI name is chosen and implemented.
    *   The server virtual environment is functional.
    *   Source files are successfully synchronized to the server.
    *   The package can be built and published to PyPI under the new name.
    *   The `README.md` is updated and reflects OSS best practices.
    *   Benchmark results (time, token, latency) for indexing the Linux kernel are documented.
    *   A GitHub Actions workflow successfully publishes a tagged release.

*   **Test Strategy:**
    *   Execute all existing unit and integration tests to ensure no regressions are introduced by bug fixes or renaming.
    *   Perform manual tests for PyPI publishing workflow.
    *   Verify server synchronization.
    *   Run the benchmarking script and validate its output.
    *   Test the GitHub Actions CI/CD pipeline by creating a test tag.

---

### Category B — Heavy Hitter: Architecture Governance Engine (5-7 days)

*   **Goal:** Implement enterprise-grade import rule governance as detailed in ADR 0010.

*   **Problem Statement:** Current import management lacks structured governance, leading to potential architectural drift, unmanageable dependencies, and security vulnerabilities. There's no systematic way to define, enforce, and report on desired import patterns.

*   **Proposed Solution:** Develop a comprehensive system for defining, analyzing, and enforcing import rules. This includes parsing rule definitions, scanning code for violations, providing CLI tools for management, generating reports on governance status, and offering diff capabilities to track changes.

*   **Components List:**
    *   **B1: YAML Parser + Schema:** For defining import rules (e.g., allowed/disallowed imports, source/destination mappings).
    *   **B2: Scanner Engine:** To traverse the codebase, parse Abstract Syntax Trees (ASTs), and identify import statements.
    *   **B3: CLI Commands:** User-facing commands for rule definition, scanning, and reporting (e.g., `ast-tools governance scan`, `ast-tools governance rules add`).
    *   **B4: Governance Diff:** Tool to compare current import structure against defined rules or previous states, highlighting violations.
    *   **B5: HTML Report Generator:** Creates a visual, human-readable report of governance status, violations, and trends.

*   **Files to Create/Modify:**
    *   `ast_tools/governance/` directory (new module for governance features)
        *   `rules.py` (YAML parsing, schema validation)
        *   `scanner.py` (AST traversal, import analysis)
        *   `cli.py` (command-line interface)
        *   `diff.py` (governance diff logic)
        *   `reporter.py` (HTML report generation)
    *   `pyproject.toml` (add dependencies like `PyYAML`, potentially `jinja2` for reports)
    *   `tests/governance/` (new test suite)
    *   `docs/specs/governance.md` (detailed documentation for the governance engine)

*   **Dependencies Between Categories:**
    *   Category B is independent of A and C, but its components (specifically the scanner engine) might leverage or inform features in Category C (like auto-fixing).
    *   Category B should ideally be developed in parallel with C, but delivered alongside D2 (Ast-grep MCP optional adapter) for launch.

*   **Acceptance Criteria:**
    *   Users can define import governance rules in YAML format.
    *   The scanner correctly identifies import statements across various Python constructs.
    *   CLI commands allow users to scan a project, add/remove rules, and view governance status.
    *   The governance diff tool accurately highlights deviations from defined rules.
    *   An HTML report is generated, clearly visualizing policy compliance and violations.

*   **Test Strategy:**
    *   Unit tests for the YAML parser and schema validation.
    *   Unit tests for the AST-based scanner, covering various import scenarios (absolute, relative, aliased, dynamic).
    *   Integration tests for CLI commands, simulating user interactions.
    *   Tests for the diff algorithm, using predefined rule sets and code states.
    *   End-to-end tests generating HTML reports from sample projects with varying rule compliance.
    *   Focus on edge cases: complex/nested imports, various Python versions, different project structures.

---

### Category C — 2 Killer Features (3-4 days)

*   **Goal:** Introduce high-impact features that differentiate ast-tools significantly.

*   **Problem Statement:** To make ast-tools truly compelling and indispensable, it needs advanced capabilities beyond basic code analysis. Specifically, automated code correction and enhanced search/ranking mechanisms would provide immense value.

*   **Proposed Solution:**
    *   **C1: Auto-fix Pipeline (`ast fix` command):** Develop a command that automates the process of validating syntax, applying lints, suggesting/applying fixes, and reformatting code. This will leverage existing linting tools and ast-tools' own analysis capabilities.
    *   **C2: Reranker Integration:** Integrate a cross-encoder model on top of the existing 6-factor RRF (Ranked-Retrieval Fusion) to improve the relevance and quality of search results, especially for complex queries.
    *   **C3: Architecture HTML Dashboard:** Create an interactive visualization of the project's import architecture using libraries like D3.js or Sigma.js, comparing actual imports against intended architecture.

*   **Components List:**
    *   **C1:**
        *   Core `ast fix` command logic.
        *   Integration with linters (e.g., Ruff, Flake8).
        *   AST modification functions for applying fixes.
        *   Code reformatting integration (e.g., Black, isort).
        *   User interaction/confirmation mechanism for fixes.
    *   **C2:**
        *   Cross-encoder model integration (loading, inference).
        *   RRF scoring modification to include cross-encoder output.
        *   Search query processing pipeline updates.
    *   **C3:**
        *   Data extraction for actual vs. intended imports.
        *   Graph data structure generation.
        *   Frontend implementation (HTML, JavaScript) using D3.js/Sigma.js.
        *   API endpoints or data files to feed the dashboard.

*   **Files to Create/Modify:**
    *   `ast_tools/fix/` (new module for auto-fix)
        *   `__init__.py`
        *   `pipeline.py`
        *   `linters.py`
        *   `formatter.py`
    *   `ast_tools/search/reranker.py` (new module for cross-encoder integration)
    *   `ast_tools/dashboard/` (new module for architecture dashboard)
        *   `generator.py`
        *   `templates/dashboard.html`
        *   `static/js/graph.js` (D3.js/Sigma.js logic)
    *   `ast_tools/code_analysis/graph.py` (potential updates for intended architecture representation)
    *   `pyproject.toml` (add dependencies: ML libraries for reranker, JS charting libraries)
    *   `tests/fix/`, `tests/search/reranker/`, `tests/dashboard/` (new test suites)
    *   `docs/specs/auto_fix.md`, `docs/specs/reranker.md`, `docs/specs/dashboard.md`

*   **Dependencies Between Categories:**
    *   Category C is independent of A and B.
    *   C1 (Auto-fix) could potentially benefit from or inform the scanner in Category B.
    *   C3 (Dashboard) benefits from robust import analysis, similar to what Category B aims to govern.

*   **Acceptance Criteria:**
    *   The `ast fix` command can be invoked, correctly identifies linting errors, and applies fixes for common issues (e.g., unused imports, formatting, simple syntax errors).
    *   The reranker demonstrably improves the quality of search results compared to RRF alone, validated by sample queries.
    *   The Architecture HTML Dashboard loads and displays an interactive graph, allowing exploration of import relationships.
    *   The dashboard accurately reflects the project's current import structure and allows for comparison with an intended architecture.

*   **Test Strategy:**
    *   **C1:** Create a diverse set of test Python files with known linting errors and syntax issues. Verify that `ast fix` correctly identifies, suggests, and applies fixes, and that the code remains valid and formatted. Test with various combinations of linters and formatters.
    *   **C2:** Develop a benchmark dataset of search queries and expected results. Evaluate the reranked results against the baseline RRF results using relevance metrics. Test with different cross-encoder models if applicable.
    *   **C3:** Generate sample project structures with defined intended architectures. Ensure the dashboard renders correctly, is interactive, and accurately visualizes the import graph. Test with varying graph complexities.

---

### Category D — Launch Prep (1-2 days)

*   **Goal:** Finalize all aspects required for a successful public launch of ast-tools v0.2.0.

*   **Problem Statement:** Beyond core feature development and bug fixing, a successful public launch requires comprehensive documentation for diverse users, streamlined deployment, and broad compatibility.

*   **Proposed Solution:**
    *   **D1: Multi-agent Onboarding Docs:** Create clear, concise documentation tailored for different AI agent/IDE environments (Claude Code, Gemini CLI, Cursor, Cline, Windsurf) to facilitate their integration and use of ast-tools.
    *   **D2: Ast-grep MCP Optional Adapter:** Develop an adapter or integration layer enabling ast-tools to work alongside or utilize `ast-grep`, providing users with more options for static analysis. This is crucial for leveraging existing ecosystems.
    *   **D3: PyPI Publish v0.2.0:** Officially publish version 0.2.0 to PyPI, incorporating all features and fixes from A, B, and C.
    *   **D4: Multi-arch Build:** Ensure the tool can be built and distributed for multiple architectures (x86_64, aarch64) and potentially as a static binary for wider compatibility (e.g., Windows).

*   **Components List:**
    *   **D1:** Documentation guides, tutorials, example snippets for each target agent.
    *   **D2:** An optional Python package or a set of compatible APIs/functions that bridge ast-tools and ast-grep.
    *   **D3:** Final packaging scripts, release notes, versioning management.
    *   **D4:** Build system configuration (e.g., `pyproject.toml` build settings, Dockerfiles for cross-compilation) to support x86_64, aarch64, and possibly Windows static builds.

*   **Files to Create/Modify:**
    *   `docs/onboarding/` (new directory for multi-agent docs)
    *   `ast_tools/adapters/astgrep.py` (new file for adapter)
    *   `CONTRIBUTING.md` (update with adapter info)
    *   `pyproject.toml` (update build settings for multi-arch)
    *   `Dockerfile` (add multi-arch build targets)
    *   Release scripts for v0.2.0.
    *   Update `README.md` and `docs/` to reference v0.2.0 and adapter information.

*   **Dependencies Between Categories:**
    *   Category D is entirely dependent on the completion of Category A (as A ensures release readiness).
    *   D2 specifically relies on the robust scanner developed in Category B, and potentially the auto-fix pipeline from Category C.
    *   D3 requires successful completion of A, B, and C.

*   **Acceptance Criteria:**
    *   Onboarding documentation is clear, accurate, and covers all specified agents.
    *   The ast-grep adapter functions correctly, allowing ast-tools to interoperate with ast-grep.
    *   Version 0.2.0 is successfully published to PyPI.
    *   Binaries or installable packages for ast-tools are successfully built for x86_64 and aarch64 architectures. (Windows static binary availability is a stretch goal).

*   **Test Strategy:**
    *   **D1:** Review by target audience representatives (if possible) or peer review for clarity and completeness.
    *   **D2:** Integration tests pairing ast-tools with ast-grep in various scenarios.
    *   **D3:** Successful installation from PyPI, verification of version number.
    *   **D4:** Build process validation on target architectures. Install and run basic tool commands on each architecture to confirm functionality.

---

### Dependency Graph:

```
   +-----------------+
   | Category A:     |
   | Ship & Polish   |
   +-------+---------+
           | (A before D)
   +-------+---------+
   | Category D:     |
   | Launch Prep     |
   +-------+---------+

   +-----------------+     +-----------------+
   | Category B:     | --> | Category D (D2) |
   | Arch Governance |     +-----------------+
   +-----------------+
           | (B informs D2)
           |
   +-----------------+     +-----------------+
   | Category C:     | --> | Category D (D2) |
   | Killer Features |     +-----------------+
   +-----------------+
           | (C informs D2)
           |
 (B and C are independent of each other and A)
```
*Note: Category B and C are developed independently of each other and Category A. However, Category B's scanner and potentially Category C's auto-fix pipeline are prerequisites for the ast-grep adapter in D2. Category A must complete before Category D begins.*
