# Tool Discovery System v1 — Code Mode for ast-tools

**Status:** Draft · **Date:** 2026-07-18  
**Authors:** Lucien (RapidWebs)  
**Inspired by:** Cloudflare Code Mode, RAG-MCP, MCPProxy, Agent Tool Registry  

---

## 1. The Problem

ast-tools currently registers **73 MCP tools** into the model context on every LLM call. This is approaching the degradation threshold documented across multiple benchmarks:

| Source | Threshold | Degradation |
|--------|-----------|-------------|
| RAG-MCP (May 2025) | >15 tools | Accuracy drops from ~44% → 13.6% |
| OpenAI docs | >128 tools | Hard ceiling, degradation before limit |
| StackOne benchmarks | >50 tools | Top-1 accuracy drops below 30% |
| MCPProxy analysis | >200 tools | BM25 loses discriminating power |

**The math for ast-tools:**
- 73 tools × ~250 tokens avg schema = ~18,250 tokens *before the user's request*
- That's ~9% of a 200K context window gone before any real work
- Semantic collisions: 73 descriptions with overlapping terms ("search", "analysis", "symbol", "reference")

---

## 2. Cloudflare's Solution: Code Mode

**Blog:** https://blog.cloudflare.com/code-mode-mcp/  
**Docs:** https://developers.cloudflare.com/agents/concepts/tools/  
**GitHub:** https://github.com/cloudflare/mcp

### Core Pattern

Instead of registering every API endpoint as a tool (2,500 endpoints = 1.17M tokens), Cloudflare registers **3 meta-tools** (~1,000 tokens):

```
┌─────────────────────────────────────────────┐
│  Model Context                              │
│                                             │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  │
│  │  docs   │  │  search  │  │  execute  │  │
│  └─────────┘  └──────────┘  └───────────┘  │
│       │            │              │          │
│       ▼            ▼              ▼          │
│  ┌─────────────────────────────────────┐    │
│  │         Sandboxed Worker            │    │
│  │  ┌───────────────────────────────┐  │    │
│  │  │  spec.paths filter by tag    │  │    │
│  │  │  cloudflare.request({...})   │  │    │
│  │  └───────────────────────────────┘  │    │
│  └─────────────────────────────────────┘    │
│         ▲                                   │
│  ┌──────┴───────────┐                       │
│  │  OpenAPI Spec    │   ~2M tokens           │
│  │  (on server)     │   never in context     │
│  └──────────────────┘                       │
└─────────────────────────────────────────────┘
```

### How It Works

1. Agent needs to do something with Cloudflare DNS
2. Agent calls `search({ code: `async () => spec.paths.filter(p => p.tags.includes('DNS'))`})`
3. Server runs the code in a sandbox, returns only the matching endpoints
4. Agent inspects the result, finds the right endpoint and parameters
5. Agent calls `execute({ code: `async () => cloudflare.request({ method: 'GET', path: '/...' })`})`

The full API spec never enters the model context. The agent discovers what it needs by writing code against a typed representation.

### Key Design Principles from Cloudflare

1. **Fixed token footprint** — regardless of API size
2. **Progressive discovery** — agent searches for what it needs, when it needs it
3. **Server-side execution** — code runs in a sandbox, results are summarized
4. **Zero agent-side changes** — new endpoints are automatically discoverable
5. **Safe execution** — sandboxed isolate with no network access to credentials

---

## 3. Design for ast-tools

### 3.1 Architecture

```
┌──────────────────────────────────────────────────┐
│  Model Context (~800 tokens)                     │
│                                                   │
│  ┌──────────────┐  ┌────────────┐  ┌───────────┐│
│  │ search_tools │  │ call_tool  │  │ tool_info ││
│  └──────────────┘  └────────────┘  └───────────┘│
│         │               │              │          │
└─────────┼───────────────┼──────────────┼──────────┘
          │               │              │
          ▼               ▼              ▼
┌──────────────────────────────────────────────────┐
│              Tool Discovery Layer                 │
│                                                   │
│  ┌────────────────────────────────────────────┐   │
│  │  Semantic Tool Registry                    │   │
│  │  ┌────────┐ ┌──────────┐ ┌──────────────┐│   │
│  │  │  FTS5  │ │  Vector  │ │  6-factor    ││   │
│  │  │  index │ │  index   │ │  RRF fusion  ││   │
│  │  └────────┘ └──────────┘ └──────────────┘│   │
│  └────────────────────────────────────────────┘   │
│         │             │             │              │
│         ▼             ▼             ▼              │
│  ┌────────────────────────────────────────────┐   │
│  │  73 Registered Tools (on server)           │   │
│  │  ast_grep, ast_read, impact_analysis, ... │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  ┌────────────────────────────────────────────┐   │
│  │  Tool Categories (for routing)             │   │
│  │  CODE_ANALYSIS | SEARCH | REFACTOR | ...  │   │
│  └────────────────────────────────────────────┘   │
│                                                   │
│  ┌────────────────────────────────────────────┐   │
│  │  Usage Analytics                            │   │
│  │  call_count, error_rate, latency_p50...   │   │
│  └────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

### 3.2 The 3 Meta-Tools

#### Tool 1: `search_tools`

```json
{
  "name": "search_tools",
  "description": "Search available tools by natural language query. Returns ranked tool names, descriptions, and schemas. Use this to discover which tool to call.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Natural language query describing what you want to do"
      },
      "category": {
        "type": "string",
        "enum": ["CODE_ANALYSIS", "SEARCH", "REFACTOR", "INDEX", "LSP", "GRAPH", "META", "FIX"],
        "description": "Optional category filter to narrow results"
      },
      "top_k": {
        "type": "integer",
        "default": 5,
        "description": "Number of tool matches to return (max 10)"
      }
    },
    "required": ["query"]
  }
}
```

**Returns:** Ranked list of matching tools with name, description, and parameter schema.

#### Tool 2: `call_tool`

```json
{
  "name": "call_tool",
  "description": "Execute a discovered tool by name. First use search_tools to find the right tool, then call it here. The tool runs in the ast-tools MCP server and returns results.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "description": "The exact tool name (from search_tools results)"
      },
      "arguments": {
        "type": "object",
        "description": "Tool-specific arguments per the schema returned by search_tools"
      }
    },
    "required": ["name", "arguments"]
  }
}
```

#### Tool 3: `tool_info`

```json
{
  "name": "tool_info",
  "description": "Get full details about a specific tool including its complete schema, usage examples, and success rate.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "description": "The exact tool name"
      },
      "include_examples": {
        "type": "boolean",
        "default": false,
        "description": "Include usage examples from the tool's documentation"
      }
    },
    "required": ["name"]
  }
}
```

### 3.3 Semantic Tool Registry

Reuses ast-tools' existing infrastructure:

| Component | What | Status |
|-----------|------|--------|
| **FTS5 index** | Keyword search over tool names + descriptions | ✅ Already built for codebase |
| **Vector index** | Embedding search over tool descriptions | ✅ Already built for codebase |
| **6-factor RRF** | Rank fusion: semantic (40%) + recency (15%) + usage (15%) + kind (10%) + proximity (10%) + centrality (10%) | ✅ Already built |
| **Tool metadata** | Schema, category, usage stats | 🏗️ Need to add |
| **Usage analytics** | call_count, error_rate, latency | 🏗️ Need to add |

### 3.4 Tool Categories

Every tool gets assigned a category at registration:

| Category | Example Tools |
|----------|--------------|
| `CODE_ANALYSIS` | ast_grep, structural_analysis, find_references |
| `SEARCH` | semantic_search, search_symbols, find_symbol_definition |
| `REFACTOR` | ast_edit, ts_edit, ast_refactor_extract_interface |
| `INDEX` | refresh_index, reindex_path, index_status |
| `LSP` | lsp_definition, lsp_hover, lsp_completion |
| `GRAPH` | kg_query, kg_neighborhood, kg_shortest_path |
| `FIX` | fix_code, fix_check, llm_suggest_fix |
| `META` | search_tools, call_tool, tool_info |
| `CURATOR` | curator_audit, curator_summary, curator_status |
| `WATCH` | watch_add, watch_status |

### 3.5 Hybrid Search Pipeline

```
User Query: "find all references to this function"
         │
         ▼
┌────────────────────┐
│  Query Embedding   │
│  (bge-small-en-v1.5) │
└────────┬───────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│  FTS5  │ │ Vector │
│ match  │ │  sim   │
└────┬───┘ └───┬────┘
     │         │
     └────┬────┘
          ▼
┌─────────────────┐
│  6-factor RRF   │
│  + usage boost  │
│  + recency      │
└────────┬────────┘
         ▼
┌─────────────────┐
│  Top-5 tools    │
│  with schemas   │
└─────────────────┘
```

### 3.6 Usage-Aware Ranking

Track per tool:

- `call_count` — how many times called
- `success_count` — how many succeeded without error
- `error_count` — how many threw
- `avg_latency_ms` — average response time
- `last_called` — timestamp of last use

**Ranking boost formula:**

```
boost = 0
if success_rate > 0.9: boost += 0.1
if call_count > 100:   boost += 0.05
if last_called < 7d:   boost += 0.03

final_score = rrf_score * (1 + boost)
```

Downrank tools with:
- Error rate > 20%
- Never called in 30+ days

---

## 4. Implementation Phases

### Phase A: Tool Registry Metadata (2-3 days)

- [ ] Add `ToolMetadata` dataclass: name, description, schema, category, usage_stats
- [ ] Annotate all 73 tools with categories in their registration
- [ ] Build FTS5 + vector index over tool descriptions
- [ ] Add `search_tools` MCP tool

### Phase B: Dispatch Layer (2-3 days)

- [ ] Build `ToolDispatcher` — validates tool name, resolves to handler, calls it
- [ ] Add `call_tool` MCP tool with argument validation
- [ ] Add `tool_info` MCP tool for full schema details
- [ ] Usage tracking: log calls, successes, errors, latency

### Phase C: Smart Ranking (1-2 days)

- [ ] Integrate usage stats into RRF scoring
- [ ] Auto-downrank failing tools
- [ ] Category-aware boosting
- [ ] Weekly staleness recalculation

### Phase D: Agent Integration (1-2 days)

- [ ] Update Hermes MCP config to use discovery layer
- [ ] Add documentation and examples
- [ ] Benchmark: 73 tools in context vs 3 meta-tools
- [ ] Progressive disclosure: load tool schemas lazily

**Total estimated effort: 6-10 days**

---

## 5. Behavior Changes

### Before (current)
```python
# Every LLM call gets 73 tool schemas (~18K tokens)
# Model sees ALL tools at all times
ast_grep, ast_read, ast_edit, structural_analysis, ...
```

### After (with discovery layer)
```python
# Every LLM call gets 3 meta-tool schemas (~800 tokens)
# Model calls search_tools("find references") → gets 3 relevant tools
# Model calls call_tool("find_references", {...}) → gets results
# The 70+ tool schemas never enter the context
```

### Migration Path

1. Phase A+B: Both paths available simultaneously
2. Phase C+D: Discovery layer becomes primary, direct tool exposure deprecated
3. Eventually: Tools like `ast_grep` still exist on the server, but the model only sees them through the discovery layer

---

## 6. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Discovery latency (embedding query) | Medium | Low | FTS5 fallback <1ms |
| Tool mis-selection (wrong tool returned) | Medium | Medium | 6-factor RRF + usage stats |
| Agent prefers direct tools (old patterns) | High | Low | Deprecate direct exposure gradually |
| Ranking cold start (no usage data) | High | Low | Seed with keyword-based defaults |
| sandbox complexity | Low | High | Start without sandbox: just dispatch |

---

## 7. Open Questions

1. **Sandbox or no sandbox?** — Cloudflare runs code in a Dynamic Worker sandbox. For ast-tools, we can start without sandboxing (just dispatch calls) and add sandboxing later.

2. **Gradual or cut-over?** — Should we keep all 73 tools registered AND add the 3 meta-tools, or remove the 73 and force agents through discovery? **Recommendation:** Both paths for Phase A+B, then cut over.

3. **How does Hermes handle this?** — Hermes loads all MCP tool schemas into context. The discovery layer would need to be configured as the primary interface, with the 73 tools configured but hidden from the model's active tool list.

4. **Recursive tools?** — `call_tool` could dispatch to itself. Add a guard: `call_tool` cannot dispatch to `call_tool`, `search_tools`, or `tool_info`.

5. **Tool schema size optimization?** — Cloudflare uses ~400 tokens per meta-tool schema. For ast-tools, each tool schema averages ~250 tokens. We can provide minimal schemas in search results and full schemas only on `tool_info` requests.

---

## 8. References

- [Cloudflare Code Mode Blog](https://blog.cloudflare.com/code-mode-mcp/)
- [Cloudflare Agents — Tools Concept](https://developers.cloudflare.com/agents/concepts/tools/)
- [Cloudflare MCP Server (GitHub)](https://github.com/cloudflare/mcp)
- [RAG-MCP Paper (May 2025)](https://doi.org/10.3390/a19060447)
- [MCPProxy — Beyond BM25](https://dev.to/algis/beyond-bm25-the-future-of-mcp-tool-discovery-57d7)
- [Agent Tool Registry (NEO)](https://heyneo.com/blog/agent-tool-registry)
- [Agent Patterns — Tool Registry](https://www.agentpatternscatalog.org/patterns/tool-agent-registry/)
- [Machine Learning Mastery — Tool Selection Guide](https://machinelearningmastery.com/the-complete-guide-to-tool-selection-in-ai-agents/)
- [StackOne MCP Benchmarks](https://stackone.com/)
- [Stacklok MCP Optimizer](https://stacklok.com/)
