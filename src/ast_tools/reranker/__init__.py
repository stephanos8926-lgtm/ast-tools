"""
Cross-encoder reranker for semantic search.

Provides a lazy-loaded CrossEncoder wrapper that integrates
into the existing semantic_search pipeline as a post-RRF
reranking step. Gracefully degrades if the model is unavailable
or the sentence-transformers library is not installed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default model - small, fast, good quality
DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
FALLBACK_MODELS = [
    "cross-encoder/ms-marco-TinyBERT-L-2-v2",  # Smaller fallback
    "cross-encoder/ms-marco-MiniLM-L-4-v2",  # Mid-range fallback
]

# Confidence threshold computation constants
CONFIDENCE_WEIGHTS = {
    "max_score": 0.4,
    "top3_avg": 0.3,
    "median": 0.3,
}


@dataclass
class RerankerConfig:
    """Configuration for the cross-encoder reranker."""

    model_name: str = DEFAULT_RERANKER_MODEL
    use_reranker: bool = False
    batch_size: int = 32
    max_candidates: int = 60  # Max candidates to rerank
    top_k: int = 15  # Return top K after reranking
    compute_confidence: bool = True
    fallback_to_rrf: bool = True  # Graceful fallback


@dataclass
class RerankResult:
    """Result of a reranking operation."""

    scores: list[float]
    indices: list[int]  # Original indices in sorted order
    confidence: float = 0.0
    model_used: str = ""
    fallback_used: bool = False
    error: str | None = None


class CrossEncoderReranker:
    """Lazy-loaded CrossEncoder wrapper with graceful fallback."""

    def __init__(self, config: RerankerConfig | None = None):
        self.config = config or RerankerConfig()
        self._model = None
        self._load_error: str | None = None

    @property
    def model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is None and self._load_error is None:
            self._load_model()
        return self._model

    def _load_model(self):
        """Try to load the cross-encoder model."""
        models_to_try = [self.config.model_name, *FALLBACK_MODELS]

        for model_name in models_to_try:
            try:
                from sentence_transformers import CrossEncoder

                logger.info(f"Loading cross-encoder model: {model_name}")
                self._model = CrossEncoder(model_name, max_length=512)
                self.config.model_name = model_name
                logger.info(f"Cross-encoder model loaded: {model_name}")
                return
            except ImportError:
                self._load_error = (
                    "sentence-transformers not installed. "
                    "Install with: uv pip install sentence-transformers"
                )
                logger.warning(self._load_error)
                return
            except Exception as e:
                logger.warning(f"Failed to load model {model_name}: {e}")
                self._load_error = str(e)
                continue

        if self._model is None:
            self._load_error = f"Could not load any cross-encoder model. Tried: {models_to_try}"
            logger.error(self._load_error)

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        score_key: str = "content",
    ) -> RerankResult:
        """Rerank candidates by relevance to query.

        Args:
            query: The search query
            candidates: List of candidate dicts with 'content' or score_key
            score_key: Key to extract text for scoring

        Returns:
            RerankResult with scores, indices, and confidence
        """
        if not candidates:
            return RerankResult(
                scores=[], indices=[], fallback_used=False, model_used=self.config.model_name
            )

        # Limit candidates
        candidates = candidates[: self.config.max_candidates]

        if self.model is None:
            # Fallback: return original order with identity scores
            return RerankResult(
                scores=[1.0 / (i + 1) for i in range(len(candidates))],
                indices=list(range(len(candidates))),
                confidence=0.0,
                fallback_used=True,
                error=self._load_error,
                model_used="none (fallback)",
            )

        try:
            # Prepare pairs
            pairs = [
                (query, c.get(score_key, c.get("text", c.get("content", "")))) for c in candidates
            ]

            # Score all pairs
            scores = self.model.predict(
                pairs, batch_size=self.config.batch_size, show_progress_bar=False
            )

            # Convert to list of floats
            score_list = [float(s) for s in scores]

            # Get sorted indices (descending)
            sorted_indices = sorted(
                range(len(score_list)),
                key=lambda i: score_list[i],
                reverse=True,
            )

            # Compute confidence
            confidence = 0.0
            if self.config.compute_confidence and score_list:
                confidence = self._compute_confidence(score_list)

            return RerankResult(
                scores=score_list,
                indices=sorted_indices[: self.config.top_k],
                confidence=confidence,
                fallback_used=False,
                model_used=self.config.model_name,
            )

        except Exception as e:
            error_msg = f"Reranking failed: {e}"
            logger.error(error_msg)

            if self.config.fallback_to_rrf:
                return RerankResult(
                    scores=[1.0 / (i + 1) for i in range(len(candidates))],
                    indices=list(range(min(len(candidates), self.config.top_k))),
                    confidence=0.0,
                    fallback_used=True,
                    error=error_msg,
                    model_used="none (fallback)",
                )

            return RerankResult(
                scores=[],
                indices=[],
                confidence=0.0,
                fallback_used=False,
                error=error_msg,
                model_used=self.config.model_name,
            )

    def is_available(self) -> bool:
        """Check if the reranker is available."""
        return self.model is not None

    @staticmethod
    def _compute_confidence(scores: list[float]) -> float:
        """Compute a confidence score from reranker scores.

        Uses a blend of max score, top-3 average, and median.
        """
        import math

        if not scores:
            return 0.0

        sorted_scores = sorted(scores, reverse=True)
        max_score = sorted_scores[0]
        top3_avg = sum(sorted_scores[:3]) / min(len(sorted_scores), 3)
        median = sorted_scores[len(sorted_scores) // 2]

        blended = (
            CONFIDENCE_WEIGHTS["max_score"] * max_score
            + CONFIDENCE_WEIGHTS["top3_avg"] * top3_avg
            + CONFIDENCE_WEIGHTS["median"] * median
        )

        # Sigmoid to [0, 1]
        return 1.0 / (1.0 + math.exp(-blended))


def apply_reranking(
    query: str,
    candidates: list[dict[str, Any]],
    config: RerankerConfig | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """Apply reranking to search results.

    Integrates the cross-encoder reranker into the existing
    semantic search pipeline as a post-processing step.

    Args:
        query: The search query
        candidates: List of candidate dicts
        config: Optional reranker config

    Returns:
        Tuple of (reranked_candidates, confidence_score)
    """
    cfg = config or RerankerConfig()

    if not cfg.use_reranker:
        return candidates, 0.0

    reranker = CrossEncoderReranker(cfg)
    result = reranker.rerank(query, candidates)

    # Reorder candidates by reranker scores
    reranked = [candidates[i] for i in result.indices if i < len(candidates)]

    # Preserve original scores and add reranker scores
    for i, idx in enumerate(result.indices):
        if i < len(reranked) and idx < len(candidates):
            if "rerank_score" not in reranked[i]:
                reranked[i]["rerank_score"] = (
                    result.scores[idx] if idx < len(result.scores) else 0.0
                )

    return reranked, result.confidence
