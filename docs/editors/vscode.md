# VS Code Extension — ast-tools

Language server extension providing structural code analysis, auto-fix, and LLM-assisted fixes for Python, TypeScript, JavaScript, Go, Rust, C++, and Markdown.

## Quick Start

```bash
# 1. Install ast-tools
pip install ast-tools

# 2. Install extension
# Download .vsix from Releases or build:
cd packages/vscode-ast-tools
npm install && npm run package

# 3. Install in VS Code
# Extensions → ... → Install from VSIX → select ast-tools-0.2.0.vsix
```

Open any supported file — diagnostics appear automatically, code actions on 💡.

## Features

| Feature | How |
|---------|-----|
| **Inline diagnostics** | Ruff, ESLint, gofmt, rustfmt, clang-format results as you type |
| **Quick fixes** | Click 💡 → apply individual fix |
| **Fix All** | `ast-tools: Run Fix All on Workspace` or `Ctrl+Alt+F` |
| **Organize Imports** | Available as code action for Python/TS/Go/Rust |
| **Format on save** | Enable via `ast-tools.fixOnSave` setting |
| **LLM fixes** | 🤖 AI-suggested fixes for diagnostics (requires API key) |
| **Multi-language** | Python, TypeScript, JavaScript, Go, Rust, C++, Markdown |

## Settings

Open VS Code Settings (`Ctrl+,`) and search for `ast-tools`:

| Setting | Default | Description |
|---------|---------|-------------|
| `ast-tools.enable` | `true` | Enable LSP server |
| `ast-tools.configPath` | `""` | Path to `ast-tools.yaml` (auto-detect if empty) |
| `ast-tools.fixOnSave` | `false` | Run auto-fix pipeline on save |
| `ast-tools.llmFixes` | `true` | Show LLM-assisted fix suggestions |
| `ast-tools.trace.server` | `"off"` | LSP trace level for debugging |

## Commands

| Command | Keybinding | Description |
|---------|-----------|-------------|
| `ast-tools: Restart LSP Server` | — | Restart language server |
| `ast-tools: Run Fix All` | `Ctrl+Alt+F` | Fix all fixable issues in file |
| `ast-tools: Open Config` | — | Open `ast-tools.yaml` |
| `ast-tools: 🤖 Suggest LLM Fix` | — | AI fix for current diagnostic |

## Config File

Create `ast-tools.yaml` in project root:

```yaml
lsp:
  diagnostics:
    enabled: true
    debounce_ms: 300
    max_diagnostics_per_file: 100
  formatting:
    format_on_save: true
    fix_on_save: false
  llm:
    enabled: true
    prefer_local: false
    remote_provider: openrouter
    remote_model: qwen/qwen-2.5-coder-32b-instruct
```

## LLM Fixes

Requires an API key in environment:

```bash
# OpenRouter (recommended)
export OPENROUTER_API_KEY="sk-..."

# Or Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Or Google Gemini
export GOOGLE_API_KEY="AIza..."
```

When enabled, diagnostics get an additional `🤖 AI: Suggest fix` code action. The LLM generates a unified diff, validated against the original content before applying.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Status bar shows $(error) disconnected | `ast-tools` not on PATH | `pip install ast-tools`, restart VS Code |
| No diagnostics | LSP not started for this language | Check supported file types list |
| LLM fixes not showing | No API key or LLM disabled | Set `OPENROUTER_API_KEY`, enable `ast-tools.llmFixes` |
| Slow diagnostics | Large file | Increase `debounce_ms` in config |

## Building from Source

```bash
git clone https://github.com/stephanos8926-lgtm/ast-tools.git
cd ast-tools/packages/vscode-ast-tools
npm install
npm run compile
npm run package          # → ast-tools-0.2.0.vsix
```
