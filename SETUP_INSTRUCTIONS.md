# Hermes Configuration Updates for AST-Tools Context Injection

## Step 1: Update ~/.hermes/config.yaml

Add the following configuration to enable AST-Tools hooks:

```yaml
# Add to the 'hooks:' section in your config.yaml
hooks:
  # ... existing hooks ...
  pre_llm_call:
  - path: /home/sysop/.hermes/plugins/ast_tools_context
    type: plugin
  pre_tool_call:
  - path: /home/sysop/.hermes/shell-hooks/ast-tools-policy.sh
    type: shell
  post_tool_call:
  - path: /home/sysop/.hermes/plugins/ast_tools_tokens
    type: plugin
```

## Step 2: Enable AST-Tools Plugins

Enable the plugins via Hermes CLI:

```bash
hermes plugins enable ast_tools_context
hermes plugins enable ast_tools_tokens
```

Or manually edit the config:

```yaml
plugins:
  enabled:
    - ast_tools_context
    - ast_tools_tokens
```

## Step 3: Add AST-Tools MCP Server

If not already added, configure the MCP server:

```yaml
mcp_servers:
  ast_tools:
    command: python3
    args:
      - /home/sysop/Workspaces/ast-tools/src/ast_tools_server.py
    enabled: true
    timeout: 120
    supports_parallel_tool_calls: false
    tools:
      include:  # Optional: filter which tools to expose
        - ast_grep
        - ast_edit
        - ast_read
        - structural_analysis
        - impact_analysis
        - semantic_search
        - find_references
        - module_imports
        - ast_generate_stub
        - refresh_index
        - index_status
```

## Step 4: Verify Shell Hook Permissions

Make the shell hook executable:

```bash
chmod +x /home/sysop/.hermes/shell-hooks/ast-tools-policy.sh
```

## Step 5: Reload Configuration

Reload hooks and MCP servers:

```bash
hermes reload-hooks
hermes reload-mcp
```

## Testing

Verify the integration:

1. **Test context injection**: Ask "How can I search for function definitions in my codebase?"
   - Should inject AST-Tools capabilities document
   
2. **Test policy enforcement**: Try `ast_grep` with pattern containing "password"
   - Should be blocked by shell hook
   
3. **Verify tool execution**: Run actual ast-grep search
   - Should execute normally and return results

4. **Check token tracking**: Run structural_analysis on large codebase
   - Check logs for token usage warnings

## Created Files

| File | Purpose |
|------|---------|
| `~/.hermes/plugins/ast_tools_context/__init__.py` | Pre-LLM-call context injection |
| `~/.hermes/plugins/ast_tools_context/plugin.yaml` | Plugin metadata |
| `~/.hermes/plugins/ast_tools_tokens/__init__.py` | Token tracking & compression warnings |
| `~/.hermes/plugins/ast_tools_tokens/plugin.yaml` | Plugin metadata |
| `~/.hermes/shell-hooks/ast-tools-policy.sh` | Pre-tool-call policy enforcement |
| `~/.hermes/shell-hooks-allowlist.json` | Shell hook allowlist |
| `/home/sysop/Workspaces/ast-tools/RESEARCH_HERMES_MCP_CONTEXT_INJECTION.md` | Full research documentation |

## Architecture Summary

```
User Query → pre_llm_call Hook → AST-Tools Context Injection → LLM
              ↓
      Tool Call → pre_tool_call Hook → Shell Policy Check → MCP Tool → post_tool_call Hook → Token Tracking
              ↓
      Result → LLM Context → Compression Check → Response
```

See `RESEARCH_HERMES_MCP_CONTEXT_INJECTION.md` for complete architecture details and patterns.