"""Transformer model for generating embeddings.

Uses sentence-transformers with all-MiniLM-L6-v2 model for CPU-efficient embedding generation.
Optimized for low RAM usage (<400MB) on constrained hardware.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from ast_tools.config.unified import RUNTIME

logger = logging.getLogger(__name__)

# Model configuration - now sourced from RUNTIME
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "ast-tools" / "models" / RUNTIME.embedding_model_minilm

# Global model cache (lazy-loaded)
_model: SentenceTransformer | None = None


def get_model(cache_dir: str | None = None) -> SentenceTransformer:
    """Load or return cached embedding model.

    Model is loaded on first call, not at import time. First call may take
    10-15s to download and load sentence-transformers (~130MB).

    Args:
        cache_dir: Optional custom cache directory for model weights.
                  Defaults to ~/.cache/ast-tools/models/{MODEL_NAME}/

    Returns:
        Loaded SentenceTransformer instance
    """
    global _model
    if _model is not None:
        return _model

    from sentence_transformers import SentenceTransformer

    cache_path = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    cache_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading embedding model: {RUNTIME.embedding_model_minilm} from {cache_path}")

    try:
        _model = SentenceTransformer(RUNTIME.embedding_model_minilm, cache_folder=str(cache_path))
        logger.info(f"Model loaded successfully (dimension: {RUNTIME.embedding_dim})")
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        raise RuntimeError(
            f"Failed to load embedding model '{RUNTIME.embedding_model_minilm}'. "
            f"Possible causes:\n"
            f"  - No internet connection (required for first download)\n"
            f"  - HuggingFace rate limiting (set HF_TOKEN for higher limits)\n"
            f"  - Disk full ({cache_path} needs ~130MB)\n"
            f"  - Corrupted cache (try deleting {cache_path} and retry)\n"
            f"Original error: {e}"
        ) from e
    return _model


def generate_embedding(text: str, model: SentenceTransformer | None = None) -> list[float]:
    """Generate embedding for a single text (docstring + signature).

    Args:
        text: Text to embed (typically "signature docstring" for symbols)
        model: Optional pre-loaded model (uses global cache if None)

    Returns:
        Embedding as list of floats (384 dimensions)

    Note:
        - Empty strings return zero vector (all 0.0)
        - Very long texts (>512 tokens) are truncated by the model
        - CPU-only inference (~20ms per embedding on i3)
    """
    if model is None:
        model = get_model()

    # Handle empty input
    if not text or not text.strip():
        return [0.0] * RUNTIME.embedding_dim

    try:
        embedding = model.encode([text], convert_to_numpy=True, normalize_embeddings=True)[0]
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return [0.0] * RUNTIME.embedding_dim


def generate_batch_embeddings(
    texts: list[str],
    model: SentenceTransformer | None = None,
    batch_size: int | None = None,
) -> list[list[float]]:
    """Generate embeddings for multiple texts in batches.

    Args:
        texts: List of texts to embed
        model: Optional pre-loaded model (uses global cache if None)
        batch_size: Batch size for processing. Defaults to RUNTIME.batch_size_embeddings_default.

    Returns:
        List of embeddings, one per input text
    """
    if model is None:
        model = get_model()

    if batch_size is None:
        batch_size = RUNTIME.batch_size_embeddings_default

    if not texts:
        return []

    # Handle empty strings
    results = []
    for text in texts:
        if not text or not text.strip():
            results.append([0.0] * RUNTIME.embedding_dim)
        else:
            results.append(None)  # Placeholder for actual embedding

    # Process non-empty texts in batches
    non_empty = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
    for i in range(0, len(non_empty), batch_size):
        batch = non_empty[i:i + batch_size]
        indices = [idx for idx, _ in batch]
        batch_texts = [t for _, t in batch]

        try:
            embeddings = model.encode(
                batch_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=batch_size,
            )
            for idx, emb in zip(indices, embeddings):
                results[idx] = emb.tolist()
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            for idx in indices:
                results[idx] = [0.0] * RUNTIME.embedding_dim

    return results


def unload_model() -> None:
    """Unload the embedding model from memory to free RAM."""
    global _model
    if _model is not None:
        del _model
        _model = None
        logger.info("Embedding model unloaded, RAM freed")
    else:
        logger.debug("No embedding model loaded, nothing to unload")