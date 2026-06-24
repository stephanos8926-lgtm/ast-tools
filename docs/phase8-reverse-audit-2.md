## 3. Performance Gotchas

### ⚠️ Gap 4: Embedding Model Load Time

**Issue:** `bge-small-en-v1.5` takes 2-3 seconds to load on first use.

**Impact:** First search feels slow (5s total: 3s load + 2s search).

**Fix:** Lazy-load model in module singleton:

```python
# src/ast_tools/embeddings/model.py
_MODEL_CACHE = None

def get_model():
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        _MODEL_CACHE = SentenceTransformer('bge-small-en-v1.5')
    return _MODEL_CACHE
```

**Already implemented?** ✅ Yes, check if this pattern exists.

---

### ⚠️ Gap 5: Vector Search on Large Indices

**Scenario:** Index has 50,000+ symbols (large project).

**Issue:** sqlite-vec KNN search is O(n) without index.

**Benchmark estimate:**
- 1,000 symbols: ~1ms
- 10,000 symbols: ~10ms
- 100,000 symbols: ~100ms (noticeable lag)

**Fixes:**
1. **HNSW index** (sqlite-vec supports it):
   ```sql
   CREATE VIRTUAL TABLE symbols_vec USING vec0(
     symbol_id TEXT PRIMARY KEY,
     embedding FLOAT[384],
     metric_type=cosine
   );
   ```

2. **Pre-filter by keyword** (hybrid search):
   - Run FTS5 first → get 100 candidates
   - Run vector search on 100 candidates only
   - Much faster than full KNN

**Recommendation:** Start with pre-filter (easier), add HNSW if needed.

---

## 4. Edge Cases in Scoring

### ⚠️ Gap 6: Recency Score Overflow

**Issue:** `exp(-days / 30)` overflows for very old symbols (>1000 days).

**Fix:** Clamp:
```python
recency_score = max(0.01, exp(-days / 30))  # Floor at 0.01
```

---

### ⚠️ Gap 7: Division by Zero in Usage Frequency

**Issue:** `log(1 + references_count) / log(1 + max_refs)` fails if `max_refs = 0`.

**Fix:**
```python
max_refs = max(1, max_references_in_dataset)
usage_score = log(1 + ref_count) / log(1 + max_refs)
```

---

### ⚠️ Gap 8: Kind Boost Hardcoding

**Issue:** Weights assume `class`/`function` always more important than `variable`.

**Counter-example:** Query "API_KEY constant" → should boost `constant` kind.

**Fix:** Detect query intent:
```python
if any(tok in query.lower() for tok in ['constant', 'variable', 'config']):
    kind_weights['constant'] = 1.0
    kind_weights['variable'] = 0.8
```

**Simpler fix:** Accept imperfect defaults, let user tune in config.

---

## 5. Token Counting Accuracy

### ⚠️ Gap 9: Token Estimates Are Guesses

**Current assumption:** 1 symbol = 300 tokens.

**Reality:**
- Simple function: ~50 tokens
- Complex class with docstring: ~500 tokens
- Class + methods + examples: ~1000+ tokens

**Risk:** Over-inject context, hit LLM limit unexpectedly.

**Fixes:**
1. **Accurate:** Use `tiktoken` per-symbol (slow but accurate)
2. **Hybrid:** Cache token counts per symbol after first compute
3. **Conservative:** Assume 500 tokens/symbol, inject fewer

**Recommendation:** Hybrid approach.

```python
# src/ast_tools/context/formatters.py
_TOKEN_CACHE: dict[str, int] = {}

def count_tokens(text: str) -> int:
    if text not in _TOKEN_CACHE:
        _TOKEN_CACHE[text] = len(tiktoken.get_encoding('cl100k_base').encode(text))
    return _TOKEN_CACHE[text]
```

---

## 6. Testing Blind Spots

### ⚠️ Gap 10: No Test for Hermes Hook Integration

**Issue:** Can't unit-test shell hooks easily.

**Risk:** Hook fails silently in production.

**Mitigation:**
1. Test hook inline first (before enabling in config)
2. Add logging to hook (stderr only)
3. Provide manual test script for user

**Test script:**
```bash
#!/bin/bash
# ~/.hermes/scripts/test-context-hook.sh
export ASTOOLS_DB_PATH=/home/sysop/Workspaces/ast-tools/.ast-tools/index.db
export ASTOOLS_QUERY="authentication"
export HERMES_CONTEXT_FILE=/tmp/test_context.md

./context-injector-hook.sh

echo "=== Injected Context ==="
cat /tmp/test_context.md
```

---

### ⚠️ Gap 11: No Test for Diversity Enforcement

**Issue:** Edge case where top 10 symbols all from same file.

**Test case:**
```python
def test_diversity_enforcement():
    # Mock: all symbols from same file
    symbols = [MockSymbol(file='same.py') for _ in range(10)]
    result = injector.select_top_k(symbols, k=10, diversity_limit=3)
    assert len(result) <= 3  # Only 3 from same file
    assert file_counts['same.py'] == 3
```

---

## 7. Configuration Validation

### ⚠️ Gap 12: No Config Validation

**Issue:** User could set invalid weights in `.ast-tools/context.yaml`:

```yaml
weights:
  semantic: 2.0  # Must be 0-1
  recency: -0.5  # NEGATIVE?!
```

**Fix:** Validate on load:

```python
def validate_config(config: dict) -> None:
    weights = config.get('weights', {})
    total = sum(weights.values())
    if not 0.95 <= total <= 1.05:
        raise ValueError(f"Weights must sum to 1.0, got {total}")
    
    for key, val in weights.items():
        if not 0.0 <= val <= 1.5:
            raise ValueError(f"Weight {key}={val} out of range [0, 1.5]")
```

---

## 8. Fallback Behavior

### ⚠️ Gap 13: What If sqlite-vec Fails?

**Scenario:** sqlite-vec extension fails to load (old SQLite version).

**Current behavior:** Logs warning, continues without vector search.

**Desired behavior:** Graceful degradation:
1. Log warning: "sqlite-vec not available, using keyword-only search"
2. Disable semantic scoring
3. Fall back to FTS5-only relevance (recency + usage + kind)

**Implementation:**
```python
# src/ast_tools/context/injector.py
def __init__(self, db_path: Path, ...):
    self.vec_available = False
    conn = get_connection(db_path)
    try:
        load_vec_extension(conn)
        self.vec_available = True
    except ImportError:
        logger.warning("sqlite-vec not available, semantic search disabled")
```

---

## Summary of Required Fixes

| Gap | Severity | Fix Complexity |
|-----|----------|----------------|
| 1. Conan tokens | Low | Trivial (pip install) |
| 2. numpy import | Medium | Trivial (check requirements) |
| 3. Hook security | High | Medium (template + review) |
| 4. Model load time | Medium | Easy (singleton caching) |
| 5. Large index perf | Medium | Medium (pre-filter or HNSW) |
| 6-8. Scoring edge cases | Low | Easy (clamping + guards) |
| 9. Token accuracy | Medium | Easy (tiktoken caching) |
| 10-11. Test gaps | High | Medium (write tests) |
| 12. Config validation | Medium | Easy (validation function) |
| 13. sqlite-vec fallback | High | Easy (feature detection) |

**Total gaps:** 13 across 5 categories
**Blockers:** None (all fixable during implementation)
**High priority:** 3, 10, 11, 13 (security, testing, fallback)

---

## Next Step: Synthesis

Combine forward + reverse audits into implementation plan.