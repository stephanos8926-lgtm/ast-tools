## Deployment + Launch Plan for ast-tools

This document outlines the plan for deploying and launching ast-tools, focusing on tasks related to Category D (Launch Prep) from the master specification.

### Dependencies on Other Categories:

*   **Category A (Rename):** This plan assumes that "Category A" (referring to the rename of ast-tools) has been completed prior to the PyPI release (D3).

### D1: Multi-Agent Onboarding Docs

*   **Description:** Create comprehensive onboarding documentation for various agents, including configuration instructions and example queries.
*   **Files to Create/Modify:** `docs/ONBOARDING.md`
*   **Content Requirements:**
    *   For each agent (Claude Code, Gemini CLI, Cursor, Cline, Windsurf, Hermes):
        *   MCP configuration instructions.
        *   2-3 line configuration excerpt.
        *   3 example queries.
*   **Verification:** Manually review the created `docs/ONBOARDING.md` file for clarity, accuracy, and completeness of the required sections.

### D2: Ast-grep MCP Compat Adapter

*   **Description:** Develop an optional adapter to enable ast-grep users to leverage the full ast-tools stack.
*   **Files to Create/Modify:** `src/ast_tools/adapters/ast_grep_bridge.py`
*   **Content Requirements:**
    *   Implement a lightweight translation layer mapping ast-grep's `find_code`, `find_code_by_rule`, `dump_syntax_tree`, and `test_match_code_rule` to ast-tools equivalents.
    *   Ensure no hard dependency on ast-grep is introduced.
*   **Verification:** 
    *   Unit tests for `src/ast_tools/adapters/ast_grep_bridge.py` should pass.
    *   Manual testing with ast-grep commands translated through the adapter.

### D3: PyPI Release v0.2.0

*   **Description:** Prepare and release version 0.2.0 of ast-tools to PyPI.
*   **Prerequisite:** Completion of Category A (Rename).
*   **Steps:**
    1.  Execute `uv build`.
    2.  Execute `uv publish`.
    3.  Create a GitHub release with the associated changelog.
*   **Verification:** 
    *   Check PyPI for the presence of `ast-tools` version 0.2.0.
    *   Verify the GitHub release notes accurately reflect the changes in this version.

### D4: Multi-Arch Build

*   **Description:** Implement a Continuous Integration/Continuous Deployment (CI/CD) matrix for multi-architecture builds and ensure compatibility.
*   **Target Architectures:** x86_64 and aarch64 (Linux).
*   **Key Considerations:** Ensure `sentence-transformers` functions correctly on ARM architecture.
*   **Files to Create/Modify:** `Dockerfile` (ensure multi-arch support).
*   **Verification:** 
    *   CI/CD pipelines successfully build for both x86_64 and aarch64.
    *   Tests pass on both architectures.
    *   Manual verification of `sentence-transformers` functionality on an aarch64 environment.

### Rollback Plan:

*   **PyPI Release (D3):** If issues arise post-release, revert to the previous stable version by unpublishing the release (if feasible and within PyPI guidelines) or by disallowing new installations of v0.2.0 and preparing an immediate hotfix release (v0.2.1).
*   **Code Changes (D1, D2, D4):** Rollback can be achieved by reverting the relevant commits on the main branch and repointing the deployment pipeline to the previous stable commit. In case of the adapter (D2), it can be temporarily disabled or removed from the build process.
*   **Documentation (D1):** Incorrect documentation can be corrected by pushing updated files and/or creating a new release at the documentation site.

### Overall Launch Readiness Checklist:

*   [ ] All launch-critical bugs resolved.
*   [ ] Comprehensive test suite passing.
*   [ ] Documentation complete and accurate.
*   [ ] CI/CD pipeline stable for all target architectures.
*   [ ] PyPI release process verified.

This plan will be iteratively refined as development progresses.
