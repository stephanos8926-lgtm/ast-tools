# F4 LSP Server — Phase 4: Editor Integration & Distribution

**Phase:** 4 of 5
**Duration:** 2 days
**Dependencies:** Phase 1-3 complete
**Status:** Planned

---

## Scope

Create editor extensions and installation tooling for VS Code, Neovim, Zed, and CLI distribution.

---

## Deliverables

### 1. VS Code Extension — `packages/vscode-ast-tools`

```
packages/vscode-ast-tools/
├── package.json
├── src/
│   ├── extension.ts
│   ├── client.ts
│   ├── configuration.ts
│   └── statusBar.ts
├── .vscode/
│   ├── launch.json
│   └── tasks.json
├── tsconfig.json
├── eslint.config.js
└── README.md
```

**Key Features:**
- Auto-starts `ast-tools lsp` via stdio
- Configuration UI for `ast-tools.yaml` settings
- Status bar indicator (connected/disconnected/indexing)
- Commands: "Restart LSP", "Open Config", "Run Fix All"
- `codeActionsOnSave` integration for fix-on-save
- Multi-root workspace support

**package.json capabilities:**
```json
{
  "name": "ast-tools",
  "publisher": "rapidwebs",
  "version": "0.2.0",
  "engines": { "vscode": "^1.80.0" },
  "categories": ["Linters", "Formatters", "Other"],
  "activationEvents": [
    "onLanguage:python",
    "onLanguage:typescript",
    "onLanguage:javascript",
    "onLanguage:go",
    "onLanguage:rust",
    "onLanguage:cpp",
    "onLanguage:markdown"
  ],
  "main": "./out/extension.js",
  "contributes": {
    "configuration": {
      "type": "object",
      "title": "ast-tools",
      "properties": {
        "ast-tools.enable": { "type": "boolean", "default": true },
        "ast-tools.configPath": { "type": "string", "default": "" },
        "ast-tools.trace.server": { "type": "string", "enum": ["off", "messages", "verbose"], "default": "off" }
      }
    },
    "commands": [
      { "command": "ast-tools.restart", "title": "Restart ast-tools LSP" },
      { "command": "ast-tools.openConfig", "title": "Open ast-tools Config" },
      { "command": "ast-tools.fixAll", "title": "Run Fix All on Workspace" }
    ]
  },
  "scripts": {
    "vscode:prepublish": "npm run compile",
    "compile": "tsc -p ./",
    "watch": "tsc -watch -p ./",
    "lint": "eslint src --ext ts",
    "package": "vsce package"
  }
}
```

### 2. Neovim Configuration — `docs/editors/nvim-lspconfig.md`

```lua
-- nvim-lspconfig setup
require'lspconfig'.ast_tools.setup{
  cmd = {'ast-tools', 'lsp'},
  filetypes = {'python', 'typescript', 'javascript', 'go', 'rust', 'cpp', 'markdown'},
  root_dir = require'lspconfig'.util.root_pattern('ast-tools.yaml', 'pyproject.toml', '.git'),
  settings = {
    ast_tools = {
      enable = true,
      configPath = '',
    }
  },
  on_attach = function(client, bufnr)
    -- Enable format on save
    if client.supports_method('textDocument/formatting') then
      vim.api.nvim_create_autocmd('BufWritePre', {
        buffer = bufnr,
        callback = function() vim.lsp.buf.format({ async = false }) end
      })
    end
  end
}
```

### 3. Zed Extension — `packages/zed-ast-tools`

```toml
# extension.toml
name = "ast-tools"
version = "0.2.0"
description = "Structural code analysis and auto-fix for Zed"
authors = ["RapidWebs"]

[language_servers.ast-tools]
command = "ast-tools"
args = ["lsp"]
extensions = ["py", "ts", "tsx", "js", "jsx", "go", "rs", "cpp", "cc", "c", "h", "hpp", "md", "mdx"]
root_markers = ["ast-tools.yaml", "pyproject.toml", ".git"]
```

### 4. CLI Distribution

**PyPI Package:** `ast-tools[lsp]` extra
```toml
# pyproject.toml
[project.optional-dependencies]
lsp = [
    "pygls>=2.1.0",
    "lsprotocol>=2024.0.0",
    "watchdog>=4.0.0",
]
llm-local = [
    "llama-cpp-python>=0.2.0",
]
llm-remote = [
    "openai>=1.0.0",
    "anthropic>=0.20.0",
    "google-generativeai>=0.5.0",
]
```

**Installation:**
```bash
pip install ast-tools[lsp]           # Core LSP
pip install ast-tools[lsp,llm-local] # + Local LLM
pip install ast-tools[lsp,llm-remote] # + Remote LLM
pip install ast-tools[lsp,llm-local,llm-remote] # Everything
```

**Binary Release (via uv/pipx):**
```bash
# Standalone install
pipx install ast-tools[lsp]
ast-tools lsp --help
```

### 5. Documentation

| File | Purpose |
|------|---------|
| `docs/editors/vscode.md` | VS Code setup, config, troubleshooting |
| `docs/editors/neovim.md` | Neovim lspconfig, keymaps, format on save |
| `docs/editors/zed.md` | Zed extension install, config |
| `docs/editors/other.md` | Generic LSP client instructions |
| `docs/lsp/configuration.md` | All LSP config options reference |
| `docs/lsp/troubleshooting.md` | Common issues and fixes |

---

## Tests Required

| Test | Description |
|------|-------------|
| `test_vscode_extension_load` | Extension activates, starts LSP |
| `test_vscode_config_ui` | Settings panel works |
| `test_vscode_fix_on_save` | Format on save triggers fix pipeline |
| `test_nvim_lspconfig` | Neovim attaches, diagnostics appear |
| `test_zed_extension` | Zed detects language server |
| `test_pip_install_lsp` | `pip install ast-tools[lsp]` works |
| `test_cli_lsp_command` | `ast-tools lsp` starts server |

---

## Acceptance Criteria

- [ ] VS Code extension installs from `.vsix`, activates on supported languages
- [ ] VS Code shows diagnostics, code actions, formatting
- [ ] VS Code "Fix All" command works
- [ ] Neovim lspconfig attaches, shows diagnostics
- [ ] Zed extension works (or documented manual setup)
- [ ] `pip install ast-tools[lsp]` installs all deps
- [ ] `ast-tools lsp` runs as standalone server
- [ ] All editor docs published
- [ ] All Phase 1-4 tests pass