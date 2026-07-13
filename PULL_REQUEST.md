# feat: Multi-signal spectral clustering for module decomposition

## Summary

Adds a `suggest_modules` tool that partitions a codebase's dependency graph into cohesive module groups using the **Fiedler vector** (2nd eigenvector of the normalized graph Laplacian). Supports 7 programming languages and fuses **4 signal sources** into a single weighted adjacency matrix.

## Pipeline

```
suggest_modules(project_root, ...)
  │
  ├── Import graph (always on)            ← ast.parse + tree-sitter
  ├── Call graph (optional, DB-backed)    ← symbol edges from index
  ├── Semantic affinity (optional)        ← embedding cosine similarity
  ├── Co-change (optional)                ← git Jaccard co-occurrence
  │
  ├── All sources fused → weighted adjacency
  └── Laplacian → Fiedler vector → recursive bipartition → clusters
```

## Edge Sources

| Source | Weight | Requires | When to Use |
|--------|--------|----------|-------------|
| Import graph | 1.0 (base) | Nothing | Always on — handles 7 languages |
| Call graph | calls=1.0, imports=0.7, inherits=0.5, inst=0.5 | ast-tools indexed DB | If you've run `ast-tools index` |
| Semantic affinity | `semantic_weight` (rec 0.2–0.5) | sentence-transformers | When modules have meaningful docs |
| Co-change | `cochange_weight` (rec 0.3–0.6) | Git history | On main branches with active cross-module work |
| Submodule containment | 0.3 | Nothing | Always on |
| Directory proximity | 0.15 | Nothing | Always on |

## Multi-Language Support

7 languages via tree-sitter query extraction + ast.parse for Python:

| Language | Files | Import Query |
|----------|-------|-------------|
| Python | .py | `ast.parse` (stdlib) |
| TypeScript | .ts, .tsx | `(import_statement source: (string (string_fragment)) @path)` |
| JavaScript | .js, .jsx, .mjs, .cjs | Same as TS |
| Go | .go | `(import_spec path: (interpreted_string_literal) @path)` |
| Rust | .rs | `(use_declaration (scoped_identifier) @path)` |
| C | .c, .h | `(preproc_include (string_literal (string_content)) @path)` |
| C++ | .cpp, .cc, .cxx, .hpp, .hh | Same as C |

Import path resolvers handle:
- TS/JS: `./relative/path` → `.ts/.tsx/.js/.jsx` extension probing + index fallback
- Go: Full import paths → directory matching
- Rust: `crate::mod::sub` → `path/to/mod.rs`; `super::`, `self::` also supported
- C/C++: Quoted includes → relative to source file + project root

## New Public API

### `suggest_modules(project_root, ...)` → `SpectralResult`

```python
# Minimal (import graph only)
result = suggest_modules("src/ast_tools")

# All signals
from ast_tools.tools.spectral import SpectralConfig
config = SpectralConfig(
    project_root="src/ast_tools",
    use_call_graph=True,
    semantic_weight=0.3,
    cochange_weight=0.4,
)
result = suggest_modules(config=config)

# Report
for c in result.clusters:
    print(f"  {c.name:<30s}  {c.size:>2} modules  cohesion={c.cohesion:.3f}")
```

### Via MCP tool

```json
{
    "project_root": "src/ast_tools",
    "semantic_weight": 0.3,
    "cochange_weight": 0.4
}
```

## New Data Structures

- **`SpectralConfig`** — Dataclass encapsulating all 9 configuration parameters. `from_dict()` factory for MCP interoperability. Recommended over individual kwargs.
- **`SpectralResult`** — Top-level result with `clusters` (list of `ClusterAssignment`), `partition_tree`, `quality` (modularity Q), `algebraic_connectivity` (λ₂).
- **`ClusterAssignment`** — Single cluster with `cluster_id`, `name` (derived from common module prefix), `modules`, `size`, `cohesion`, `coupling`.

## Cluster Naming

Clusters are automatically named from the longest common prefix of their module paths:

```
[ast_tools.tools.spectral, ast_tools.tools.dependency]  → "ast_tools.tools"
[frontend.app, frontend.components.button]               → "frontend"
[helpers]                                                → "helpers"
```

Duplicate names are disambiguated with `_2`, `_3` suffixes. Mixed-prefix clusters fall back to `cluster_<id>`.

## Tests — 43 passing (was 25)

```
Core algorithm:       13  (Laplacian, Fiedler, quality, bipartition)
Integration:           7  (synthetic project, MCP tool)
Multi-language:        7  (Python, TS, Go, Rust, C, C++, mixed)
Semantic & co-change: 11  (graceful fallbacks, git repo, SpectralConfig, from_dict)
Edge cases:            3  (empty, isomorphic, nonexistent)
```

## Benchmark (ast-tools, 121 modules)

| Mode | Time | Clusters | Q | Notes |
|------|------|----------|---|-------|
| Import only | **0.25s** | 75 | 0.09 | Baseline — very fast |
| + Call graph | 0.23s | 75 | 0.09 | Falls back instantly w/o DB |
| + Semantic | 26.1s | 118 | 0.00 | Model load dominates; threshold 0.5 too high for short tool files |
| + Co-change | 0.00s | — | — | 0 edges on narrow feature branch (expected) |

**Key finding**: Fiedler vector computation is 0.0008s on 121×121 dense. The bottleneck for large projects (>500 modules) would benefit from scipy sparse eigensolver (~10× acceleration).

## Dependencies

- **Core**: `numpy` only
- **Optional `[spectral]` extra** (pip install ast-tools[spectral]):
  - `scipy>=1.9.0` — faster eigensolver for large graphs
  - `tree-sitter>=0.23` + grammars for Python/TS/Go/Rust/C/C++ — multi-language import extraction

## Files Changed

| File | Change |
|------|--------|
| `src/ast_tools/tools/spectral.py` | +1749 lines — core algorithm + multi-lang + call graph + semantic + co-change + config + naming |
| `src/ast_tools/tools/__init__.py` | +9 lines — updated MCP tool schema with 3 new params |
| `tests/test_spectral.py` | +408 lines — 18 new tests (multi-lang, semantic, co-change, config, naming) |
| `pyproject.toml` | +7 lines — updated `[spectral]` dependency group with tree-sitter grammars |
