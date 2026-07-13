# VS Code Extension for ast-tools — Plan

**Goal:** Ship a VS Code extension that connects to `ast-tools lsp`, delivering inline diagnostics, code actions, formatting, and LLM fix suggestions in the editor.

**Structure:**
```
packages/vscode-ast-tools/
├── package.json          # Extension manifest
├── tsconfig.json         # TypeScript config
├── src/
│   ├── extension.ts      # Activation, LSP client init
│   ├── commands.ts       # "Fix All", "Restart LSP", "Open Config"
│   └── statusBar.ts      # Connection status indicator
├── .vscode/
│   ├── launch.json       # Debug config
│   └── tasks.json        # Build tasks
├── .eslintrc.json
└── README.md
```

**Dependencies:** `vscode-languageclient` (LSP client), `typescript` (dev)

**Key behaviors:**
- Activates on Python/TS/JS/Go/Rust/C++/Markdown files
- Starts `ast-tools lsp` via stdio transport
- Registers: diagnostics, code actions, formatting, fix-on-save
- Status bar: connected/disconnected/indexing
- Commands: "Restart LSP", "Run Fix All", "Open Config"
- Config UI: enable/disable, config path, trace level

**Estimated: ~300 lines of TypeScript, ~2h**

---

Want me to build it? I'll write the full extension source, install deps, and verify it compiles. No VS Code on this workstation (Zed won't launch due to GL), so we can't run it, but we can make it ready to `vsce package` on the server or your machine.