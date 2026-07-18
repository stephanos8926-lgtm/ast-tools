# Phase D — Hermes Integration: Discovery Mode

## Goal
Reduce the model's active tool list from 77 tools (~18K tokens) to 4 meta-tools (~800 tokens). The 73 individual tools remain registered and callable through `call_tool` — they're just not dumped into the LLM's context window.

## What Needs to Change

### 1. `src/ast_tools/_server.py` — Filter `list_tools()`
Add a `DISCOVERY_MODE` flag. When enabled, `handle_list_tools()` returns only the 4 meta-tools. The 73 individual tools are still registered and callable through `call_tool`.

**Trigger:** `AST_TOOLS_DISCOVERY_MODE=true` env var (not set in tests, so test suite unaffected).

### 2. `~/.hermes/config.yaml` — Add env var to MCP server config
```yaml
mcp_servers:
  ast-tools:
    args:
      - /home/sysop/Workspaces/ast-tools/src/ast_tools/_server.py
    command: /home/sysop/Workspaces/ast-tools/.venv/bin/python3
    connect_timeout: 60
    timeout: 120
    env:
      AST_TOOLS_DISCOVERY_MODE: "true"
```

### 3. No other changes needed
- `call_tool` dispatches to any registered tool regardless of discovery mode
- `search_tools` searches the full tool registry regardless of discovery mode
- Tests are unaffected (env var not set in test environment)

## Token Impact

| Mode | Tools in Context | Token Cost | Improvement |
|------|-----------------|-----------|-------------|
| Current (all tools) | 77 | ~18,000 | — |
| Discovery mode | 4 | ~800 | 95% reduction |

## Verification
After deployment:
1. `hermes` should list only 4 tools from ast-tools
2. `call_tool("ast_grep", {...})` should still work
3. `search_tools("find references")` should still return results
4. All 943 tests should pass