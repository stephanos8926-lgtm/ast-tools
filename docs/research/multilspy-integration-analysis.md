# multilspy Integration Analysis — ast-tools

**Date:** 2026-07-31  
**Author:** Lucien (RapidWebs Enterprise)  
**Source:** [microsoft/multilspy](https://github.com/microsoft/multilspy) — MIT License, ~590 stars

---

## Overview

`multilspy` is a Python LSP client library developed by Microsoft Research for the NeurIPS 2023 paper ["Monitor-Guided Decoding of Code LMs with Static Analysis of Repository Context"](https://arxiv.org/abs/2306.10763). It provides a language-agnostic interface to spawn, communicate with, and query Language Server Protocol (LSP) servers across **12+ languages**.

---

## multilspy Architecture

### Core Components

| Layer | Class | Role |
|-------|-------|------|
| **Transport** | `LanguageServerHandler` | JSON-RPC 2.0 over stdio — spawns subprocess, reads/writes headers, dispatches requests/notifications |
| **Client** | `LanguageServer` | Abstract base + factory. Language-specific subclasses provide configs (initialize params, server binary) |
| **Sync Wrapper** | `SyncLanguageServer` | Thread-based event loop bridge for synchronous contexts |
| **Language Adapters** | `JediServer`, `RustAnalyzer`, `EclipseJDTLS`, etc. | Per-language init params, server commands, capability negotiation |

### Supported Languages

| Language | Server | Binary Mgmt |
|----------|--------|-------------|
| Python | jedi-language-server | pip |
| Rust | rust-analyzer | auto-download |
| Java | Eclipse JDTLS | auto-download |
| C# | OmniSharp | auto-download |
| TypeScript/JS | TypeScriptLanguageServer | npm |
| Go | gopls | auto-download |
| C/C++ | clangd | auto |
| Dart | Dart | SDK |
| Ruby | Solargraph | gem |
| Kotlin | KotlinLanguageServer | auto-download |
| PHP | Intelephense | auto-download |
| Elixir | ElixirLS | auto |

Key feature: **auto-download of platform-specific binaries** — multilspy handles the JDTLS/Rust Analyzer/etc. download on first use.

### API Surface

```python
# Async
lsp = LanguageServer.create(config, logger, "/path/to/repo")
async with lsp.start_server():
    defs = await lsp.request_definition(file, line, col)
    refs = await lsp.request_references(file, line, col)
    hover = await lsp.request_hover(file, line, col)
    syms = await lsp.request_document_symbols(file)
    completions = await lsp.request_completions(file, line, col)

# Sync wrapper
lsp = SyncLanguageServer.create(config, logger, "/path")
with lsp.start_server():
    defs = lsp.request_definition(file, line, col)
```

---

## ast-tools Current LSP Implementation

ast-tools has **two separate LSP systems**:

### 1. MCP LSP Client Tools (`lsp_client.py` + `tools/lsp_tools.py`)

- **399-line hand-rolled** JSON-RPC client
- Spawns language servers as subprocesses via `subprocess.Popen`
- Thread-based `_read_responses()` loop with `threading.Event` for synchronous waits
- Supports 6 languages: Python, Rust, TypeScript, Go, C, C++
- Provides MCP tools: `lsp_definition`, `lsp_references`, `lsp_hover`, `lsp_symbols`, `lsp_call_hierarchy_in/out`, `lsp_available_languages`, `lsp_check_server`

#### Weaknesses
- **Hand-rolled JSON-RPC parser** — fragile Content-Length header splitting, no edge case handling
- **Thread-based sync** — no async support; blocks the event loop
- **No binary management** — users must manually install every LSP server
- **No retry/reconnection** — server crash is unrecoverable
- **No diagnostics tracking** — `lsp_diagnostics` is a stub
- **No resource cleanup guarantees** — finally blocks can fail

### 2. LSP Server (`lsp/server.py` via `pygls`)

- Built on `pygls` as an LSP **server** (serving capabilities to editors)
- Provides: diagnostics (fix engine), code actions, formatting (fix pipeline)
- **Orthogonal to multilspy** — pygls handles server-side LSP, multilspy handles client-side

---

## Comparison: Current Client vs multilspy

| Feature | Current (`lsp_client.py`) | multilspy |
|---------|--------------------------|-----------|
| **Languages** | 6 | 12+ |
| **Binary mgmt** | ❌ Manual install | ✅ Auto-download |
| **JSON-RPC** | Hand-rolled | Battle-tested |
| **Async API** | ❌ Thread-based | ✅ asyncio native |
| **Sync API** | ✅ Thread-based | ✅ Event loop bridge |
| **Capabilities** | definition, references, hover, symbols, call hierarchy | Same + completions |
| **Health/retry** | ❌ None | ❌ None (v0.0.15) |
| **File buffers** | ❌ Stateless | ✅ Open file tracking |
| **Error handling** | Basic try/except | Structured error codes |
| **Deps** | None | pip install multilspy |
| **License** | MIT | MIT |
| **Maintenance** | Self-maintained (399 LOC) | Microsoft (590 stars, 107 forks) |
| **LSP version** | Partial 3.17 | Full 3.17 |
| **Server cleanup** | Manual | Managed (shutdown + cancel tasks + close pipes) |

---

## Integration Analysis

### What multilspy Would Replace

```
Before:                    After:
lsp_client.py (399 LOC) →  multilspy (external dep)
  │                        │
  ├─ LSPClient class      ├─ LanguageServer.create()
  ├─ spawn/stop/cleanup   ├─ auto-download + managed lifecycle
  ├─ JSON-RPC parsing     ├─ LanguageServerHandler (proven)
  └─ sync thread bridge   └─ SyncLanguageServer wrapper
```

The high-level MCP tool wrappers in `tools/lsp_tools.py` would remain as they are — they'd call multilspy instead of the hand-rolled client underneath.

### What multilspy Cannot Do

- **Replace pygls** — multilspy is a client, pygls is a server framework. Our `lsp/server.py` needs pygls.
- **Tree-sitter parsing** — ast-tools' core differentiator is structural code analysis via tree-sitter, not LSP queries.
- **Semantic search / vector search** — multilspy has no knowledge graph, no embeddings, no RRF fusion.
- **Structural editing** — multilspy can't do AST-based code modification.
- **Impact analysis** — multilspy has no dependency graph traversal.

### Integration Points

| Integration Point | Effort | Value |
|-------------------|--------|-------|
| Replace `LSPClient` internals with multilspy | Medium | 12+ languages, auto-binary mgmt, proven transport |
| Add multilspy dep to pyproject.toml | Trivial | — |
| Preserve `tools/lsp_tools.py` MCP API surface | Low | Backward compatibility |
| Remove hand-rolled JSON-RPC from `lsp_client.py` | Medium | Less maintenance surface |
| Add Java/C#/Kotlin/PHP/Ruby/Dart support | Low (automatic via multilspy) | Broader language coverage |

---

## Languages Gained by Adopting multilspy

| Language | multilspy Server | Current ast-tools Support |
|----------|-----------------|--------------------------|
| Java | ✅ Eclipse JDTLS | ❌ |
| C# | ✅ OmniSharp | ❌ |
| Kotlin | ✅ KotlinLanguageServer | ❌ |
| PHP | ✅ Intelephense | ❌ |
| Dart | ✅ Dart | ❌ |
| Ruby | ✅ Solargraph | ❌ |
| Elixir | ✅ ElixirLS | ❌ |

These would immediately become available through the existing MCP tool wrappers (`lsp_definition`, `lsp_references`, etc.) without any per-language code.

---

## Risks & Considerations

### Positive
- **MIT license** — compatible with ast-tools' MIT license
- **Microsoft maintained** — active development, 590 stars
- **57 open issues** — some bugs but active triage
- **Used in research** — validated by NeurIPS publication
- **No extra deps** — pure Python, no native extensions

### Negative
- **57 open issues** — notably 35% of issue count vs stars ratio is high
- **v0.0.15** — pre-1.0, API may change
- **JDTLS requires JDK 17** — adds Java dependency, ~300MB download
- **Auto-download can fail** — network-dependent setup
- **Another external dep** — increases supply chain risk (mitigated by MIT license + pinned version)
- **Server process management** — multilspy spawns real OS processes; need to ensure cleanup on all exit paths

### Neutral
- **Async-first** — aligns with ast-tools' async MCP server architecture
- **File buffer tracking** — multilspy tracks open files; ast-tools `DocumentStore` does something similar; could consolidate

---

## Recommendation

**LOW priority integration — adopt as underlying transport layer when time permits.**

### Rationale

1. The current hand-rolled client (399 LOC) works for the 6 languages ast-tools actively needs.
2. ast-tools' core differentiators are **tree-sitter structural analysis** and **semantic search with 6-factor RRF** — not LSP client capabilities.
3. multilspy's main value is **12+ language support** and **auto-binary management**, which matter most when ast-tools needs to support Java, C#, Kotlin, PHP in user workflows.
4. If ast-tools gains IDE plugin use cases (VS Code extension, editor integration), multilspy becomes more valuable as the LSP client backbone.

### Migration Path

```python
# Current
from ast_tools.lsp_client import get_lsp_client
client = get_lsp_client(file)
client.start()
result = client.goto_definition(file, line, col)

# With multilspy
from multilspy import LanguageServer, MultilspyConfig
config = MultilspyConfig.from_dict({"code_language": detect_language(file)})
lsp = LanguageServer.create(config, logger, root_path)
async with lsp.start_server():
    result = await lsp.request_definition(file, line, col)
```

The MCP tool wrappers in `tools/lsp_tools.py` would switch their internal implementation while keeping the same MCP tool interface. No user-visible API changes.

### When to Prioritize

- ✅ If users request Java/C#/Kotlin/PHP LSP support
- ✅ If the hand-rolled JSON-RPC parser causes production bugs
- ✅ If server-binary management becomes a support burden
- ❌ **Not needed** for current Python/Rust/TS/Go/C/C++ use cases

---

## References

- multilspy: https://github.com/microsoft/multilspy
- MGD paper: https://arxiv.org/abs/2306.10763
- ast-tools LSP client: `src/ast_tools/lsp_client.py` (399 LOC)
- ast-tools LSP tools: `src/ast_tools/tools/lsp_tools.py` (430 LOC)
- ast-tools LSP server: `src/ast_tools/lsp/server.py` (457 LOC, pygls-based)
