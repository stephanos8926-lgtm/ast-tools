---
name: ast-tools
description: "Structural code analysis and editing via MCP — AST search, refactoring, dependency analysis, semantic search."
version: 1.0.0
author: RapidWebs Enterprise
tags: [mcp, code-analysis, ast, refactoring, python]
platforms: [generic]
---

# rw-ast-tools — Cross-Platform Skill

## Installation

```bash
pip install rw-ast-tools
```

## Quick Start

Run the MCP server:

```bash
ast-tools-server
```

## Server Modes

| Mode | Flag | Transport | Lifecycle | Use Case |
|------|------|-----------|-----------|----------|
| `timeout` (default) | `--mode timeout` | stdio | Per-connection, idle TTL | Desktop CLI agents |
| `daemon` | `--mode daemon` | stdio + systemd | Persistent, auto-restart | Multi-agent workstations |
| `remote` | `--mode remote` | HTTP | Persistent, auth | Server deployment |

## Tools (57 total)

**Core Tools:** `ast_grep`, `ast_read`, `ast_edit`, `ast_generate_stub`, `ast_refactor_extract_interface`, `ts_edit`

**Analysis:** `structural_analysis`, `impact_analysis`, `module_imports`, `find_references`, `find_symbol_definition`, `blast_radius_v2`, `class_hierarchy`, `circular_dependencies`, `dependency_chain`, `external_dependencies`, `dead_code_detection`, `dead_code_enhanced`

**Search:** `semantic_search` (6-factor RRF), `search_symbols`, `find_symbol_definition`, `list_symbols`, `ast_query`, `codebase_summary`, `project_info`

**Agent Integration:** `context_inject`, `context_status`, `token_status`, `validate_usage`

**Index:** `refresh_index`, `index_status`, `reindex_path`, `watch_add`, `watch_status`

**Knowledge Graph:** `kg_query`, `kg_shortest_path`, `kg_neighborhood`

**Co-Change:** `co_change_predict`, `co_change_hotspots`, `co_change_history`, `co_change_diff`

**Repository:** `api_surface_diff`, `repo_skeleton`, `file_related_suggest`, `transitive_dependents`, `code_validate_syntax`

**LSP:** `lsp_available_languages`, `lsp_check_server`, `lsp_definition`, `lsp_references`, `lsp_hover`, `lsp_symbols`, `lsp_call_hierarchy_in`, `lsp_call_hierarchy_out`

## Config Management

```bash
# Create default config
ast-tools config init

# View config
ast-tools config show

# Validate configuration
ast-tools config validate
```

## Troubleshooting

1. Ensure the project is indexed (`refresh_index`)
2. Check `ast config validate` for configuration issues
3. Verify the MCP server is running (`ast-tools-server`)