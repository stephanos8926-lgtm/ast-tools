# Neovim — ast-tools LSP Setup

Neovim LSP client configuration for the ast-tools language server. Provides inline diagnostics, code actions, formatting, and LLM-assisted fixes.

## Prerequisites

```bash
pip install ast-tools
```

## Minimum Setup (lspconfig)

```lua
-- ~/.config/nvim/lsp/ast-tools.lua
local lspconfig = require("lspconfig")

lspconfig.ast_tools.setup({
  cmd = { "ast-tools", "lsp" },
  filetypes = {
    "python", "typescript", "javascript",
    "go", "rust", "cpp", "markdown",
  },
  root_dir = lspconfig.util.root_pattern(
    "ast-tools.yaml", "pyproject.toml", ".git"
  ),
  settings = {
    ast_tools = {
      enable = true,
      configPath = "",
    },
  },
})
```

> **Note:** If `ast_tools` is not a built-in lspconfig server name, use the generic `lspconfig["ast-tools"]` or register via `lspconfig.configs.ast_tools = { ... }`.

## Full Setup with Keymaps

```lua
-- ~/.config/nvim/lsp/ast-tools.lua
local lspconfig = require("lspconfig")
local keymap = vim.keymap.set
local bufopts = { noremap = true, silent = true }

lspconfig.ast_tools.setup({
  cmd = { "ast-tools", "lsp" },
  filetypes = {
    "python", "typescript", "javascript",
    "go", "rust", "cpp", "markdown",
  },
  root_dir = lspconfig.util.root_pattern(
    "ast-tools.yaml", "pyproject.toml", ".git"
  ),
  on_attach = function(client, bufnr)
    -- Format on save
    if client.supports_method("textDocument/formatting") then
      vim.api.nvim_create_autocmd("BufWritePre", {
        buffer = bufnr,
        callback = function()
          vim.lsp.buf.format({ async = false })
        end,
      })
    end

    -- Keymaps (buffer-local)
    keymap("n", "gD", vim.lsp.buf.declaration, bufopts)
    keymap("n", "gd", vim.lsp.buf.definition, bufopts)
    keymap("n", "K", vim.lsp.buf.hover, bufopts)
    keymap("n", "gi", vim.lsp.buf.implementation, bufopts)
    keymap("n", "<leader>ca", vim.lsp.buf.code_action, bufopts)
    keymap("n", "<leader>f", function()
      vim.lsp.buf.format({ async = false })
    end, bufopts)
  end,
  capabilities = require("cmp_nvim_lsp").default_capabilities(),
  settings = {
    ast_tools = {
      enable = true,
      configPath = "",
      fixOnSave = false,
      llmFixes = true,  -- Enable LLM fix suggestions
    },
  },
})

-- Auto-start ast-tools for supported filetypes
vim.api.nvim_create_autocmd("FileType", {
  pattern = {
    "python", "typescript", "javascript",
    "go", "rust", "cpp", "markdown",
  },
  callback = function()
    vim.lsp.start({
      name = "ast-tools",
      cmd = { "ast-tools", "lsp" },
      root_dir = vim.fs.root(0, { "ast-tools.yaml", "pyproject.toml", ".git" }),
    })
  end,
})
```

## Using with mason.nvim

```lua
-- ~/.config/nvim/lsp/ast-tools.lua
require("mason-lspconfig").setup_handlers({
  ["ast_tools"] = function()
    require("lspconfig").ast_tools.setup({
      cmd = { "ast-tools", "lsp" },
      filetypes = {
        "python", "typescript", "javascript",
        "go", "rust", "cpp", "markdown",
      },
      root_dir = require("lspconfig").util.root_pattern(
        "ast-tools.yaml", "pyproject.toml", ".git"
      ),
    })
  end,
})
```

## LLM Fixes

Enable LLM-assisted fixes by setting the environment variable before starting Neovim:

```bash
export OPENROUTER_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="AIza..."

nvim
```

LLM fix suggestions appear as code actions (`<leader>ca`) on diagnostics. Each suggestion is a validated unified diff — only cleanly-applicable patches are offered.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `LSP[ast-tools]` not starting | `ast-tools` not on PATH | `pip install ast-tools` |
| No diagnostics | Wrong root_dir pattern | Add `".git"` to root_pattern |
| Format on save not working | Client doesn't support method | Check `client.supports_method("textDocument/formatting")` |
| LLM fixes not showing | No API key | Set `OPENROUTER_API_KEY` env var |

## Verify Setup

```vim
:LspInfo                     " Check ast-tools is attached
:echo luaeval("vim.lsp.get_active_clients()")  " List active clients
```

Expected: ast-tools listed as active client for supported file types.
