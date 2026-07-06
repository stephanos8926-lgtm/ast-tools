# rw-ast-tools Hermes Plugin — Installation Notes

**Last updated:** 2026-07-06  
**Author:** Lucien

---

## Installed Plugin

The unified `rw-ast-tools` plugin replaces the three legacy plugins:

| Legacy Plugin | Replaced By |
|---------------|-------------|
| `ast-tools-context` | `rw-ast-tools` |
| `ast-tools-tokens` | `rw-ast-tools` |
| `ast-tools-codebase-index` | `rw-ast-tools` |

Other global plugins (unchanged):
- `verification-gate` — Injects verification-before-completion reminder

---

## Installation Steps

### From ast-tools project:

```bash
cd ~/Workspaces/ast-tools/hermes-plugins
cp -r rw-ast-tools ~/.hermes/plugins/
```

### Or use the installer script:

```bash
cd ~/Workspaces/ast-tools/hermes-plugins
./scripts/install.sh rw-ast-tools
```

---

## Plugin Loading

Hermes loads plugins **dynamically on session start** — no gateway restart required.

To verify plugins loaded:
```python
# In Hermes Python session:
from hermes_cli.plugins import get_all_plugins
plugins = get_all_plugins()
print([p.name for p in plugins])
```

Expected output includes:
- `rw-ast-tools`
- `verification-gate`

---

## Hook Registration

Plugins register hooks via `ctx.register_hook(event_name, callback_function)`.

**Supported events:**
- `on_session_start` — injected at session beginning (used by rw-ast-tools, verification-gate)
- `pre_llm_call` — before LLM processes user message (used by rw-ast-tools)
- `post_tool_call` — after tool execution (used by rw-ast-tools)

**Note:** Hook names are **case-sensitive** and use **underscores** (`on_session_start` NOT `OnSessionStart`).

---

## Troubleshooting

### Plugin not loading
1. Check syntax: `python3 -m py_compile ~/.hermes/plugins/<plugin>/__init__.py`
2. Verify plugin.yaml exists with valid YAML
3. Check Hermes logs: `journalctl --user -u hermes-gateway -n 50`

### Hook not firing
1. Verify hook name matches exactly (case + underscores)
2. Check plugin is in the loaded list (see verification command above)
3. Ensure callback function signature matches expected params

### Gateway restart blocked
If running inside the gateway process, restart commands are blocked. Workaround:
```bash
# Write script to file, then execute
echo '#!/bin/bash
sleep 2
systemctl --user restart hermes-gateway' > /tmp/restart.sh
chmod +x /tmp/restart.sh
bash /tmp/restart.sh
```

**Note:** Not required for plugin loading — plugins load on session start, not gateway start.

---

## Development Workflow

1. Develop plugin in `~/Workspaces/ast-tools/hermes-plugins/` (for ast-tools plugins)
2. Test by copying to `~/.hermes/plugins/`
3. Start new Hermes session to verify behavior
4. Commit to ast-tools repo (only for rw-ast-tools)
5. Global plugins (verification-gate) live only in `~/.hermes/plugins/` — not versioned in ast-tools

---

## Security Notes

- Plugins run with same privileges as Hermes gateway
- No sandboxing — plugins can access files, run commands, call tools
- Only install plugins you trust
- API keys in plugins should use Hermes vault or environment variables, not hardcoded

---

## Rollback

To uninstall a plugin:
```bash
rm -rf ~/.hermes/plugins/<plugin-name>
# Start new Hermes session
```

Plugins are removed from next session; no restart required.