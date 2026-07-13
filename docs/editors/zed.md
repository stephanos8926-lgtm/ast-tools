# Zed — ast-tools LSP Setup

Zed editor configuration for the ast-tools language server. Provides inline diagnostics, code actions, and formatting.

## Prerequisites

```bash
pip install ast-tools
```

## Configuration

Add to `~/.config/zed/settings.json` (or your project's `.zed/settings.json`):

```json
{
  "lsp": {
    "ast-tools": {
      "binary": {
        "path": "ast-tools",
        "arguments": ["lsp"]
      },
      "settings": {
        "enable": true,
        "fixOnSave": false,
        "llmFixes": true
      }
    }
  },
  "languages": {
    "Python": {
      "language_servers": ["ast-tools", "pyright"]
    },
    "TypeScript": {
      "language_servers": ["ast-tools", "typescript-language-server"]
    },
    "JavaScript": {
      "language_servers": ["ast-tools", "typescript-language-server"]
    },
    "Go": {
      "language_servers": ["ast-tools", "gopls"]
    },
    "Rust": {
      "language_servers": ["ast-tools", "rust-analyzer"]
    },
    "C++": {
      "language_servers": ["ast-tools", "clangd"]
    },
    "Markdown": {
      "language_servers": ["ast-tools"]
    }
  }
}
```

## Extension (Alternative Method)

For easier management, install via the Zed extensions system. Create `~/.config/zed/extensions/ast-tools/extension.toml`:

```toml
[language_servers.ast-tools]
name = "ast-tools"
description = "Structural code analysis and auto-fix"
command = "ast-tools"
args = ["lsp"]
languages = [
  "Python",
  "TypeScript",
  "JavaScript",
  "Go",
  "Rust",
  "C++",
  "Markdown",
]

[language_servers.ast-tools.configuration]
enable = true
fixOnSave = false
llmFixes = true
```

Then enable in `settings.json`:

```json
{
  "lsp": {
    "ast-tools": {
      "initialization_options": {
        "enable": true,
        "llmFixes": true
      }
    }
  }
}
```

## Format on Save

```json
{
  "languages": {
    "Python": {
      "language_servers": ["ast-tools", "pyright"],
      "format_on_save": {
        "language_server": "ast-tools"
      }
    }
  }
}
```

## Project Config

Place `ast-tools.yaml` in your project root to customize behavior:

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

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Server not starting | `ast-tools` not on PATH | `pip install ast-tools`, restart Zed |
| No diagnostics | Language not configured | Add language to `language_servers` list |
| Format on save not working | Wrong server name | Confirm `format_on_save.language_server: "ast-tools"` |
