
# ADR-0009: Reranker Integration for ast-tools

## Status
Draft

## Context
The `ast-tools` project, with its 55 tools and over 330 tests, relies on the `semantic_search` function for code intelligence. This function currently uses a 6-factor RRF (Reciprocal Rank Fusion) for ranking, combining semantic similarity, recency, usage, kind, proximity, and call graph centrality. While effective, there's a recognized need to enhance the precision of the top-ranked results.

## Decision
To significantly improve the accuracy of the top-ranked results in `semantic_search`, a cross-encoder reranker will be introduced as a second stage. This reranker will process the top candidates identified by the initial RRF fusion, re-scoring them to produce a more refined, highly accurate top 5 results.

## Technical Approach

### Reranker Model
- **Choice:** `sentence-transformers` library's `CrossEncoder` implementation.
- **Model:** `'cross-encoder/ms-marco-MiniLM-L-6-v2'`
- **Characteristics:**
    - Optional dependency: Not strictly required for `ast-tools` to function, but needed for reranking.
    - Performance: CPU-only, approximately 80MB model size. Expects ~5-10ms per pairwise comparison.

### Integration into `semantic_search`
- **New Parameter:** A `use_reranker` boolean parameter will be added to `semantic_search` (defaulting to `false` initially).
- **Configuration:** A new section for reranker configuration will be added to `ast-tools`'s tool parameters, including:
    - `reranker_model`: Specifies the model to use (defaults to the aforementioned MiniLM model).
    - `reranker_top_k`: The number of top candidates to pass to the reranker (defaults to 20).
- **Lazy Loading:** The reranker model and its associated logic will be loaded only on the first call to `semantic_search` when `use_reranker` is enabled.
- **Model Download:** The HuggingFace Hub will be used for automatic model downloading.

### File Structure Modifications
- `src/ast_tools/reranker/__init__.py`: Exports for the new reranker functionality.
- `src/ast_tools/reranker/cross_encoder.py`: Contains the `CrossEncoder` wrapper class, handling lazy loading, model caching, and timeouts.
- `tests/test_reranker.py`: Comprehensive unit tests for the reranker functionality, following TDD principles.
- `src/ast_tools/semantic_search.py`: The integration point where the reranker call is injected after the initial RRF fusion.

### Interface Contracts
#### `semantic_search` function signature:
```python
def semantic_search(
    query: str,
    k: int = 5,
    use_reranker: bool = False,
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    reranker_top_k: int = 20,
    # ... other existing parameters
) -> SearchResults:
    # ... existing RRF logic
    if use_reranker:
        # Initialize reranker if not already loaded
        reranker = CrossEncoderReranker(model_name=reranker_model)
        # Get top_k candidates from RRF
        rerank_candidates = initial_results[:reranker_top_k]
        # Rerank candidates
        reranked_scores = reranker.score_pairs(query, rerank_candidates)
        # Combine RRF scores with reranked scores and sort
        final_results = combine_and_sort(initial_results, reranked_scores, k)
        return final_results
    else:
        return initial_results[:k]
```

#### `CrossEncoderReranker` class (conceptual):
```python
class CrossEncoderReranker:
    def __init__(self, model_name: str):
        # Lazy load model and tokenizer from sentence-transformers
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.cache = {} # Optional: for caching model instances

    def _load_model(self):
        if self.model is None:
            # Load model and tokenizer, handle potential download/caching
            # Set up CPU usage
            self.model = CrossEncoder(self.model_name, device='cpu')
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name) # Example
            self.cache[self.model_name] = self.model # Store for potential reuse

    def score_pairs(self, query: str, candidates: list[SearchResult]) -> list[float]:
        self._load_model()
        # Prepare input pairs: [(query, candidate.content) for candidate in candidates]
        # Use self.model.predict()
        # Return scores
        pass # Placeholder
```

### Test Plan
- **Unit Tests (`tests/test_reranker.py`):**
    - Test model loading (CPU device, lazy loading).
    - Test scoring with mock data and edge cases (empty candidates, long queries/candidates).
    - Test caching mechanism.
    - Test timeout handling.
- **Integration Tests (`tests/test_semantic_search.py`):**
    - Test `semantic_search` with `use_reranker=True` and compare output against baseline (without reranker).
    - Verify `reranker_top_k` parameter influences the reranker's input.
    - Test default `reranker_model` and ability to specify a different one.
    - Ensure performance impact adheres to CON constraints.
- **End-to-End Tests:**
    - Manual testing with diverse queries to subjectively evaluate the quality of top 5 results post-reranking.

## Consequences

### Positive
- **Improved Accuracy:** Significantly more accurate top-5 ranking compared to RRF alone, leading to better user experience and code intelligence.
- **Competitive Edge:** Addresses a gap in code-intelligence solutions, as no direct competitors are known to utilize rerankers for this purpose.

### Negative
- **Increased Latency:** Expect an additional ~100-200ms latency during the reranking pass for calls that enable the reranker.
- **Disk Space:** Requires ~80MB for model cache storage.
- **First-Call Download:** The initial invocation of `semantic_search` with `use_reranker=True` will incur a ~10-15 second delay due to model download.

## Options Considered

1.  **No reranker (keep 6-factor RRF only):**
    *   **Pros:** Simplest implementation, no added latency or dependencies.
    -   **Cons:** Inferior top-ranked result quality compared to a reranker; less competitive.

2.  **Cross-encoder reranker on CPU (Chosen):**
    *   **Pros:** Optimal balance between accuracy gains and performance impact. Manageable resource usage.
    -   **Cons:** Adds latency, disk usage, and a one-time download cost.

3.  **LLM-as-reranker:**
    *   **Pros:** Potentially highest accuracy.
    -   **Cons:** Prohibitively slow, too expensive for this use case, overkill for the problem.

4.  **ColBERT late interaction:**
    *   **Pros:** Faster than a cross-encoder, potentially better accuracy than RRF alone.
    -   **Cons:** More complex integration than a standard cross-encoder, accuracy gains might not justify the complexity.

