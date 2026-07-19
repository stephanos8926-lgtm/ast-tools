# AST-Tools Hermes Agent Integration

**Configures 3 Hermes plugins for code intelligence:** context injection, token budget tracking, and project-aware semantic context.

---

## Plugins Overview

| Plugin | Hooks | Purpose |
|--------|-------|---------|
| `ast-tools-context` | `pre_llm_call`, `on_session_start` | Injects tool documentation & "did you mean?" corrections on code queries |
| `ast-tools-tokens` | `pre_llm_call`, `post_tool_call` | Token budget tracking with 50%/80% pressure alerts |
| `ast-tools-project-context` | `pre_llm_call` | Injects actual project code context via `semantic_search` |

---

## Step 1: Enable Plugins in Hermes Config

Add to your Hermes config file (typically `~/.hermes/config.yaml`):

```yaml
plugins:
  enabled:
    - ast-tools-context
    - ast-tools-tokens
    - ast-tools-project-context
```

## Step 2: Add AST-Tools MCP Server

```yaml
mcp_servers:
  ast-tools:
    command: ["python3", "-m", "ast_tools_server"]
    cwd: "/path/to/ast-tools"   # Replace with your install path
    enabled: true
    timeout: 120
```

## Step 3: Install Plugin Files

```bash
# Copy plugins from the ast-tools project to your Hermes plugins directory
cp -r path/to/ast-tools/hermes-plugins/ast-tools-context ~/.hermes/plugins/
cp -r path/to/ast-tools/hermes-plugins/ast-tools-tokens ~/.hermes/plugins/
cp -r path/to/ast-tools/hermes-plugins/ast-tools-project-context ~/.hermes/plugins/
```

## Step 4: Reload & Verify

```bash
hermes plugins list | grep ast-tools
hermes reload-mcp
```

### Test context injection:
Ask: *"How can I search for function definitions in my codebase?"*
→ Should inject AST-Tools capability docs

### Test project context:
Ask: *"Where is the authentication handler?"*
→ Should inject actual project code locations

### Test token tracking:
Ask: *"Find all async functions"* on a large codebase
→ Logs should show token usage warnings

---

## Architecture

```
User Query → pre_llm_call → Plugin Injectors → AST-Tools MCP → LLM
              ↓
      Tool Call → post_tool_call → Token Tracker → Response
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Plugin not loading | Check `~/.hermes/logs/` for errors, verify plugin dir exists |
| MCP server not responding | Check logs for errors, verify path in config |
| Context not injecting | Enable verbose logging: `hermes config set log.level debug` |

See `docs/TROUBLESHOOTING.md` for full troubleshooting guide.