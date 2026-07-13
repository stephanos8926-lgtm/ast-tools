# ast-tools for VS Code

Structural code analysis, auto-fix, and LLM-assisted fixes in your editor.

## Features

- **Inline diagnostics** — Ruff, ESLint, gofmt, rustfmt, clang-format results as you type
- **Code actions** — Quick fixes, Fix All, Organize Imports, and refactoring
- **Auto-format** — Format on save for all supported languages
- **LLM fixes** — 🤖 AI-suggested fixes for diagnostics (requires API key)
- **Multi-language** — Python, TypeScript, JavaScript, Go, Rust, C++, Markdown

## Requirements

- Python 3.11+ with `ast-tools` installed:
  ```bash
  pip install ast-tools
  ```
- For LLM fixes: `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY` environment variable

## Extension Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `ast-tools.enable` | `true` | Enable the LSP server |
| `ast-tools.configPath` | `""` | Path to custom config file |
| `ast-tools.fixOnSave` | `false` | Run auto-fix on save |
| `ast-tools.llmFixes` | `true` | Show LLM fix suggestions |
| `ast-tools.trace.server` | `"off"` | LSP communication trace level |

## Commands

| Command | Keybinding | Description |
|---------|-----------|-------------|
| `ast-tools: Restart LSP Server` | — | Restart the language server |
| `ast-tools: Run Fix All on Workspace` | `Ctrl+Alt+F` | Fix all fixable issues |
| `ast-tools: Open Config File` | — | Open ast-tools.yaml |
| `ast-tools: 🤖 Suggest LLM Fix` | — | AI-suggested fix for current diagnostic |

## Config File

Create `ast-tools.yaml` in your project root:

```yaml
lsp:
  diagnostics:
    enabled: true
    debounce_ms: 300
  formatting:
    format_on_save: true
    fix_on_save: false
  llm:
    enabled: true
    prefer_local: false
    remote_provider: openrouter
    remote_model: qwen/qwen-2.5-coder-32b-instruct
```

## Building

```bash
cd packages/vscode-ast-tools
npm install
npm run compile
npm run package  # produces .vsix
```

## License

MIT