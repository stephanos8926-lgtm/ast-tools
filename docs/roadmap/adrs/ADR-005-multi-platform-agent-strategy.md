# ADR-005: Multi-Platform Agent Strategy

**Status:** Draft  
**Date:** 2026-07-31  
**Author:** Lucien  
**Deciders:** Steven Page  

## Context

AST-Tools must integrate with multiple AI coding agents (Hermes, Claude Code, Gemini CLI, Qwen Code). Each has its own extension/plugin system, tool registration format, and installation patterns. Building native extensions for all platforms at once is expensive.

## Decision

Adopt a **MCP-first + layered adapters** strategy:

### Layer 1: MCP Protocol (Universal)
The MCP server is the single truth of all functionality. Any agent that supports the MCP protocol (all major ones do) can connect to it directly. This works immediately with no adapter code.

### Layer 2: SKILL.md Bundle (Cross-Platform)
Platform-agnostic SKILL.md files that teach any agent how to use the MCP tools. These are plain markdown documents that agents load at session start. One bundle works for Hermes, Claude Code (CLAUDE.md), and any agent that supports markdown-based skill loading.

### Layer 3: Hermes Plugins (First-Class)
Full Hermes plugins with `register()` hooks, tool registration, and context injection. These provide the best experience on Hermes (auto-discovery, context-aware injection, token budget management).

### Layer 4: CLI Extensions (Other Agents)
For agents that can't load plugins or SKILL.md files (e.g., CLI-only agents), provide shell wrappers that translate agent requests to ast-tools CLI commands.

### Layer 5: Native Extensions (Future)
Full native extensions for Claude Code (CLAUDERC/CLI hooks), Gemini CLI (Gemini extensions), Qwen Code (Qwen plugins). Only build when demand justifies the cost.

### Priority Order
1. SKILL.md bundle (Phase 0) — works everywhere, minimal effort
2. Hermes plugins (Phase 0-1) — immediate value for our primary platform
3. Claude Code tuck (Phase 4) — `CLAUDE.md` file drop-in
4. Gemini CLI extension (Phase 4) — `gemini-extension.yaml`
5. Qwen Code extension (Phase 5) — lower priority

### Consequences
- Positive: Immediate compatibility with all MCP-capable agents
- Positive: SKILL.md bundle is reusable across platforms
- Positive: Layered approach means we ship value at every stage
- Negative: Hermes plugin code has a dependency on Hermes-specific APIs
- Negative: SKILL.md files must be maintained for accuracy

## Alternatives Considered
1. **Build all native extensions first**: Rejected — too expensive upfront, insufficient demand data
2. **Hermes-only**: Rejected — contradicts agent-agnostic principle
3. **SDK-only, no SKILL.md**: Rejected — SKILL.md is minimal effort for massive reach