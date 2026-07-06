---
name: ast-tools
description: "Structural code analysis and editing via MCP — AST search, refactoring, dependency analysis, semantic search."
version: 2.0.0
author: RapidWebs Enterprise
tags: [mcp, code-analysis, ast, refactoring, python]
platforms: [hermes]
---

# rw-ast-tools — Hermes Agent Skill

## Installation

```bash
pip install rw-ast-tools
# Or via uv:
uv tool install rw-ast-tools
```

## Quick Start

Start the MCP server:

```bash
ast-tools-server
```

Configure in `~/.hermes/config.yaml`:

```yaml
mcpServers:
  rw-ast-tools:
    command: ast-tools-server
    args: ["--mode", "timeout"]
```

## Hermes Plugin

The unified **rw-ast-tools** plugin replaces the 3 old plugins (ast-tools-context, ast-tools-tokens, ast-tools-codebase-index).
It lives at `~/.hermes/plugins/rw-ast-tools/` and provides:

- Auto-injected code context into LLM prompts
- Token budget management
- Session intelligence and metrics

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

## Usage

```bash
# Index a project
refresh_index project_path="."

# Search structurally
ast_grep pattern="def $FUNC($$$ARGS)" lang="python" path="src/"

# Semantic search
semantic_search query="authentication logic" k=10
```

## Troubleshooting

- **Server won't start**: Check `python3 -m ast_tools` for import errors
- **No results**: Run `refresh_index(force=True, embeddings=True)` first
- **Want daemon mode**: `ast-tools-server --mode daemon` (requires systemd installed)