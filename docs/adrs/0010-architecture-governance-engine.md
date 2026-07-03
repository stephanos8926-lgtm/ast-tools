
# ADR-0010: Architecture Governance Engine for ast-tools

## Status

Proposed

## Context

This document outlines the proposed Architecture Decision Record (ADR) for implementing an architecture governance engine within the `ast-tools` project. The need for such a system arises from the increasing complexity of managing codebases, especially those involving AI-generated code, and the competitive landscape where tools like SonarQube are already offering architecture management features. Enterprises are actively seeking solutions to govern AI-generated code at scale. `ast-tools` is well-positioned to address this gap, as it already possesses foundational capabilities such as import graph, call graph, class hierarchy analysis, transitive dependency tools, co-change analysis, and dead code detection.

The primary gap identified is the absence of a mechanism to define and enforce architectural constraints (e.g., module A can import module B but not module C) across the entire codebase. This capability is crucial for effective architecture governance.

## Decision

We will build a three-layer architecture governance engine for `ast-tools`.

### Layer 1: Architecture Definition DSL

This layer will allow users to define architectural rules using a Domain-Specific Language (DSL), with YAML serving as the primary format. Key features include:

-   **Rule Definition:** Users will define rules in a `governance.yaml` file.
    -   Example: `"core": {"allow_import": ["utils", "models"], "deny_import": ["api", "external"]}`
-   **Layer/Tagging:** Support for defining logical layers or tags for modules (e.g., `frontend`, `backend`, `core`, `shared`, `api`, `external`).
-   **Import Controls:** Explicit allowlists and denylists for imports between defined layers.
-   **Layer Boundary Definitions:** Mechanisms to clearly delineate the boundaries and dependencies between layers.

### Layer 2: Scanner

This layer will be responsible for analyzing the codebase and identifying violations of the defined architectural rules.

-   **Import Graph Reverse-Engineering:** The scanner will automatically reconstruct the current import graph of the codebase.
-   **Violation Detection:** It will compare the actual import graph against the intended architecture defined in the DSL.
-   **Reporting Violations:** Violations will be reported with detailed context, including:
    -   File path and line number.
    -   The specific rule that was violated.
    -   A suggestion for remediation.

### Layer 3: Governance CLI

A command-line interface (CLI) will provide user-friendly access to the governance engine's functionalities.

-   `ast governance init`: Initializes a new `governance.yaml` file with a basic structure.
-   `ast governance check`: Scans the current codebase against the `governance.yaml` file and reports all violations.
-   `ast governance diff`: Compares the architectural rules between two points in the commit history (e.g., before and after a refactoring).
-   `ast governance report`: Generates a human-readable (e.g., HTML) report summarizing violations, potentially with visualizations.
-   `ast governance baseline`: Analyzes the current codebase structure and generates a `governance.yaml` file that reflects the existing architecture, serving as a starting point for defining stricter rules.

## Implementation Plan

The implementation will proceed in phases:

-   **Phase 1 (2 days):** DSL Parser and YAML Schema. Develop the parser for the `governance.yaml` file and define a robust schema with validation.
-   **Phase 2 (2 days):** Scanner Engine. Implement the core logic for reverse-engineering the import graph and comparing it against the defined rules.
-   **Phase 3 (2 days):** CLI Commands. Develop the CLI commands for `init`, `check`, `report`, and `baseline`.
-   **Phase 4 (1 day):** Governance Diff. Implement the functionality to compare architectural snapshots between branches or commits.
-   **Phase 5 (1 day):** Reporting. Develop the HTML report generation, potentially integrating with libraries like D3.js, Sigma.js, or Mermaid for visualizations.

## File Structure

The following file structure is proposed within the `ast-tools` project:

```
src/
└── ast_tools/
    └── governance/
        ├── __init__.py
        ├── dsl_parser.py       # Parses and validates governance.yaml
        ├── violation.py        # Defines Violation dataclass
        ├── scanner.py          # Core scanning engine (import graph vs rules)
        └── report.py           # Generates HTML reports
tests/
└── test_governance.py      # TDD tests for all governance components

cli.py                      # Integration point for the 'ast governance' subcommand group
```

## Interface Contracts

*   **`governance.yaml` Schema:** A well-defined schema for the YAML configuration, detailing layer definitions, `allow_import`, and `deny_import` structures.
*   **`dsl_parser.py`:**
    *   `parse_governance_file(path: str) -> Dict[str, Any]`: Parses and validates the YAML file.
    *   `validate_layer_definitions(layers: Dict[str, Any]) -> bool`: Validates layer structure.
*   **`violation.py`:**
    *   `Violation(rule: str, file_path: str, line_num: int, message: str, suggestion: str)`: Dataclass for representing a violation.
*   **`scanner.py`:**
    *   `Scanner(governance_config: Dict[str, Any])`: Initializes the scanner with governance rules.
    *   `scan(codebase_path: str) -> List[Violation]`: Performs the scan and returns a list of violations.
    *   `_build_import_graph(codebase_path: str) -> Dict[str, Set[str]]`: Internal helper to build the import graph.
*   **`report.py`:**
    *   `generate_html_report(violations: List[Violation], output_path: str)`: Generates an HTML report.
*   **`cli.py`:**
    *   Subcommand group `governance` with subcommands `init`, `check`, `diff`, `report`, `baseline`.

## Acceptance Criteria

*   Users can define architectural rules using a clear YAML DSL.
*   The engine can accurately parse and validate the `governance.yaml` file.
*   The scanner can correctly build an import graph from a Python codebase.
*   The scanner accurately identifies and reports violations based on defined rules.
*   CLI commands (`init`, `check`, `baseline`) function as specified.
*   The `diff` command provides a meaningful comparison between architectural states.
*   A human-readable report is generated with violation summaries.

## Test Plan

*   Unit tests for `dsl_parser.py` covering valid and invalid YAML inputs, schema validation.
*   Mocks for AST parsing and import graph generation to unit test `scanner.py`.
*   Integration tests for the `scanner.py` with a sample project structure and defined `governance.yaml`.
*   Unit tests for CLI commands using a testing framework (e.g., `pytest`).
*   End-to-end tests simulating user workflows: init -> check -> report.
*   Tests for the `diff` functionality comparing different versions of `governance.yaml` or codebase states.
*   Tests for report generation, validating HTML output structure and content.

