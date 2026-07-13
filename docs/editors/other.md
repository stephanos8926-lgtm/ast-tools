# Generic LSP Client Setup

If your editor isn't VS Code, Neovim, or Zed, you can still use ast-tools via any LSP-compatible client. This guide covers the common patterns.

## Server Command

The ast-tools LSP server runs on stdio:

```bash
ast-tools lsp
```

Configure your editor to start it for these file types:

| Language | File Extensions |
|----------|----------------|
| Python | `.py` |
| TypeScript | `.ts`, `.tsx` |
| JavaScript | `.js`, `.jsx` |
| Go | `.go` |
| Rust | `.rs` |
| C++ | `.cpp`, `.cc`, `.cxx`, `.h`, `.hpp` |
| C | `.c` |
| Markdown | `.md`, `.mdx` |

## Root Markers

The server uses these to find the project root (first match wins):

- `ast-tools.yaml`
- `pyproject.toml`
- `.git`

## Capabilities

The server advertises:

| Feature | Method |
|---------|--------|
| Diagnostics | `textDocument/diagnostic` (pull) + `textDocument/publishDiagnostics` (push) |
| Code actions | `textDocument/codeAction` + `codeAction/resolve` |
| Formatting | `textDocument/formatting` + `textDocument/rangeFormatting` |
| Document sync | Incremental (sync kind 2) |
| Fix on save | Via `textDocument/didSave` notification |

## Configuration (DidChangeConfiguration)

The server accepts configuration via `workspace/didChangeConfiguration`:

```json
{
  "ast_tools": {
    "enable": true,
    "configPath": "",
    "fixOnSave": false,
    "llmFixes": true
  }
}
```

## Initialization Options

Pass these in `initialize` params:

```json
{
  "enable": true,
  "configPath": "",
  "fixOnSave": false,
  "llmFixes": true
}
```

## Code Actions

| Kind | Title | Description |
|------|-------|-------------|
| `quickfix` | `{tool}: {description}` | Apply individual fixer suggestion |
| `source.fixAll` | `ast-tools: Fix all (safe)` | Apply all safe fixes |
| `source.fixAll` | `ast-tools: Fix all (unsafe)` | Apply safe + unsafe fixes |
| `source.organizeImports` | `Organize imports` | Sort and organize imports |
| `refactor` | `🤖 AI: Suggest fix` | LLM-generated fix (if enabled) |

## Editor-Specific Guides

- [VS Code](vscode.md)
- [Neovim](neovim.md)
- [Zed](zed.md)

## Troubleshooting

1. **Server won't start** — `pip install ast-tools` and verify `which ast-tools`
2. **No diagnostics** — Ensure workspace has a root marker (`ast-tools.yaml`, `pyproject.toml`, or `.git`)
3. **LLM fixes not showing** — Set `OPENROUTER_API_KEY` environment variable
4. **Format on save not working** — Verify editor sends `textDocument/didSave` with text content
