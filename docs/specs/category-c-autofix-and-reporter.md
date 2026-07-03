
# Spec: Category C - Auto-fix Pipeline & Architecture Governance Reporter

This document outlines the specifications for two key features in `ast-tools`: an automated code fixing pipeline and an architecture governance reporting tool. These features aim to improve code quality, consistency, and architectural compliance.

## Part 1: Auto-fix Pipeline

### Goal

To provide a one-command `ast fix` functionality that automates the process of validating code syntax, identifying issues (syntax errors, lint violations, formatting, import organization), applying fixes, and reformatting code.

### Current State

The `ast-tools` project currently has `code_validate_syntax` which supports syntax validation for multiple languages using compilers and tree-sitter. However, there is no built-in capability for automatic code fixing or reformatting.

### Design

The `ast fix` command will orchestrate a pipeline of tools to bring code into a desired state of correctness and style.

#### Interface Contracts

*   **`ast fix [file]`**:
    *   Validates syntax using existing `code_validate_syntax`.
    *   Applies automated fixes in categories 1-4.
    *   Reformats the code.
    *   If successful, the file is modified in place.
    *   If not all issues can be fixed automatically, provides clear feedback.
*   **`ast fix --check`**:
    *   Validates syntax and identifies fixable issues without modifying files.
    *   Intended for CI environments to report on code quality and potential fixes.
    *   Exits with a non-zero status code if issues are found.
*   **`ast fix --diff [file]`**:
    *   Applies automated fixes and reformatting but outputs the changes as a diff (e.g., using a diff utility) instead of modifying the file in place.
*   **`ast fix --all`**:
    *   Applies the fix pipeline to all supported files in the project.

#### Integration with Existing Tools

The pipeline will leverage and integrate with the following tools:

*   **Syntax Validation**: `code_validate_syntax` (already exists).
*   **Structural Fixes (Python)**: `ast_edit` (internal tool, needs to be developed/leveraged).
*   **Lint Fixes (Python)**: `ruff` (specifically `ruff --fix`).
*   **Formatting**:
    *   Python: `black` or `ruff format`.
    *   JavaScript/TypeScript: `prettier`, `eslint --fix`.
    *   Go: `gofmt`, `gofumpt`.
    *   (Add other languages as supported by `ast-tools`).
*   **Import Organization**: `ruff` (specifically `ruff check --select I001 --fix` for Python).

#### Fix Categories

The pipeline will address issues in the following order:

1.  **Syntax Errors**: Feedback directly from `code_validate_syntax` will guide AST manipulation for basic syntax correction where feasible.
2.  **Lint Violations**: Fixes for stylistic and programmatic issues identified by linters (e.g., `ruff --fix`).
3.  **Formatting**: Consistent code style applied by language-specific formatters (e.g., `black`, `prettier`, `gofmt`).
4.  **Import Organization**: Ensuring imports are sorted, unique, and correctly grouped (e.g., `ruff`'s import sorting rules).

#### File Structure (within `ast-tools` repository)

```
ast-tools/
├── src/
│   └── ast_tools/
│       ├── fix/
│       │   ├── __init__.py       # FixEngine class entry point
│       │   ├── pipeline.py       # Orchestrates the fix pipeline
│       │   ├── python_fixer.py   # Python-specific fixing logic
│       │   ├── autofix_tool.py   # MCP tool wrapper for fix pipeline
│       │   └── ...               # Other language-specific fixers (e.g., js_fixer.py)
│       └── ...
├── tests/
│   └── test_fix.py             # TDD tests for the fix pipeline
└── cli/
    └── fix_command.py          # CLI integration for 'ast fix' subcommand
```

#### Acceptance Criteria

*   `ast fix [file]` successfully corrects syntax errors, lint violations, formatting, and import issues for supported languages.
*   `ast fix --check` accurately reports issues without modifying files and returns a non-zero exit code when issues exist.
*   `ast fix --diff` generates a valid diff output for proposed changes.
*   The pipeline handles multiple fix categories in the correct order.
*   The tool integrates seamlessly with existing `code_validate_syntax` functionality.
*   New files, supported languages, and additional fix categories can be extended easily.

#### Test Plan

*   **Unit Tests**: For `FixEngine`, pipeline orchestrator, and individual fixer modules. Mocking external tool calls where appropriate.
*   **Integration Tests**:
    *   Test `ast fix` on files with various combinations of syntax errors, lint violations, formatting issues, and import problems.
    *   Test `ast fix --check` in a CI-like environment.
    *   Test `ast fix --diff` and verify the output.
    *   Test with different languages supported by `ast-tools`.
*   **End-to-end Tests**:
    *   Run `ast fix --all` on the entire `ast-tools` project and verify no regressions or new issues are introduced.

---

## Part 2: Architecture HTML Report

### Goal

To generate an interactive, single-file HTML report that visualizes the current software architecture (file dependencies, import graph) and highlights violations against an intended architecture defined in `governance.yaml`.

### Design

The `ast architecture-report` command will produce a self-contained HTML file using JavaScript libraries like Sigma.js or D3.js for graph visualization.

#### Interface Contracts

*   **`ast architecture-report [--output <path>] [--governance <path>]`**:
    *   Generates a standalone HTML report.
    *   `--output`: Specifies the path to save the generated HTML file. Defaults to `./architecture-report.html`.
    *   `--governance`: Path to the `governance.yaml` file defining the intended architecture. Defaults to `./governance.yaml`.
    *   If `governance.yaml` is not found or invalid, the tool should report an error or attempt to proceed with only the current architecture graph.

#### Visualization Details

*   **Graph Type**: Interactive network graph.
*   **Libraries**: Sigma.js or D3.js for rendering.
*   **Nodes**: Represent files or modules.
*   **Edges**: Represent import dependencies.
*   **Edge/Node Styling**:
    *   Import violations (against `governance.yaml`) will be highlighted (e.g., red edges or nodes).
    *   Layer boundaries defined in `governance.yaml` will be visually distinct.
*   **Interactivity**:
    *   Zooming and panning.
    *   Hovering over nodes/edges to display details (file path, import chain, violation type).
    *   Filtering capabilities (e.g., by layer, by violation type).

#### Data Sources

1.  **Intended Architecture**: Read from `governance.yaml` (requires parsing and understanding its structure, referencing Category B work).
2.  **Current Import Graph**: Read from the project's SQLite database. This database is assumed to be populated by existing import analysis tools within `ast-tools`. The graph should represent direct and transitive import relationships.

#### Report Structure (HTML)

The generated HTML file will contain:

1.  **Header**: Report title, generation date, project name.
2.  **Overview Section**: Summary statistics (e.g., total files, total dependencies, number of violations, pass/fail status based on `governance.yaml`).
3.  **Violations List**: A tabular or list view of all detected architectural violations, with details on the violating file, the rule broken, and the intended requirement.
4.  **Dependency Graph Visualization**: The interactive graph powered by Sigma.js/D3.js.
5.  **Layer Breakdown (Optional)**: Sections detailing each architectural layer and its components.

#### Integration with Governance Engine (Category B)

*   The tool will parse `governance.yaml` to understand the intended layers, allowed dependencies between layers, and specific component rules.
*   It will compare the generated import graph against these rules to identify violations.
*   Violations will be visually marked on the graph and listed in the report.

#### Acceptance Criteria

*   `ast architecture-report` generates a valid, standalone HTML file.
*   The HTML report displays an interactive graph of the project's current import dependencies.
*   Architectural violations, as defined by `governance.yaml`, are correctly identified and highlighted on the graph and in a dedicated list.
*   The report includes an overview with key statistics and a pass/fail summary.
*   The tool successfully reads from the project's SQLite dependency database and the specified `governance.yaml` file.
*   The generated HTML has zero external dependencies (all JS/CSS inlined).

#### Test Plan

*   **Unit Tests**: For graph generation logic, violation detection algorithms, HTML templating, and parsing of `governance.yaml`.
*   **Integration Tests**:
    *   Test report generation with a sample `governance.yaml` and a mock or small database of import dependencies.
    *   Verify correct highlighting of various violation types (e.g., wrong layer import, forbidden dependency).
    *   Test the `--output` and `--governance` CLI arguments.
*   **End-to-end Tests**:
    *   Run `ast architecture-report --all` on the `ast-tools` project.
    *   Manually inspect the generated HTML report for correctness and usability.
    *   Verify that the report accurately reflects the project's architecture and governance rules.
    *   Test with a complex `governance.yaml` and a large import graph.

