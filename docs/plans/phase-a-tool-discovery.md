# Implementation Plan — Phase A: Tool Discovery System

## Deliverables

1. **ToolMetadata system** — categories + descriptions for all 73 tools
2. **search_tools** MCP tool — semantic search via FTS5 over tool descriptions
3. **call_tool** MCP tool — dispatch to any registered tool
4. **tool_info** MCP tool — full details for a specific tool

## Architecture (lightweight, no new deps)

```
tools/__init__.py          ← existing: TOOL_REGISTRY, register_tool()
  + TOOL_METADATA dict     ← new: name → {category, description, schema}
  + search_tools()         ← new: FTS5-based tool discovery
  + call_tool()            ← new: validate + dispatch
  + tool_info()            ← new: full schema + metadata
```

## File Changes

### 1. `src/ast_tools/tools/__init__.py`
- Add `TOOL_METADATA` dict: `name → {category, description, schema, usage_stats}`
- Import 73 tools categories from a new `_tool_categories.py`
- Add `search_tools(query, category, top_k)` — FTS5 via temp sqlite3 index
- Add `call_tool(name, arguments)` — validates name, finds handler, dispatches
- Add `tool_info(name, include_examples)` — returns full metadata
- Register all 3 new tools via `register_tool()`

### 2. `src/ast_tools/tools/_tool_categories.py` (NEW)
- One dict mapping every registered tool name to its category
- 10 categories total (CODE_ANALYSIS, SEARCH, REFACTOR, etc.)

### 3. No schema changes — `TOOL_SCHEMAS` already has everything we need

## FTS5 Index Strategy

For 73 tools, FTS5 via a temporary in-memory sqlite3 is sufficient:
- Build at import time
- FIELDS: name, description, category
- Query: BM25 scoring
- No embedding model needed at this scale (BM25 gives 87% top-5 for <200 tools)

## Implementation Order

1. Create `_tool_categories.py` with category assignments
2. Add `TOOL_METADATA` and the 3 new functions to `__init__.py`
3. Register the 3 discovery tools
4. Test end-to-end
5. Commit

## Tests

- Test `search_tools` returns correct tools for various queries
- Test `call_tool` dispatches correctly
- Test `tool_info` returns full schema
- Test `register_tool` now accepts metadata

## Resource Budget

- 528MB RAM available — FTS5 on 73 tools uses <1MB
- No new Python dependencies
- No embedding model loading (starts cold)
