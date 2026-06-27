"""Transformer model for generating embeddings.

Uses sentence-transformers with all-MiniLM-L6-v2 model for CPU-efficient embedding generation.
Optimized for low RAM usage (<400MB) on constrained hardware.
"""

import logging
import os
from pathlib import Path

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Model configuration
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Batch size configuration (via env var for flexibility)
# Default 16 for safety on 4GB RAM systems; can be increased via AST_TOOLS_EMBEDDING_BATCH_SIZE
DEFAULT_BATCH_SIZE = int(os.environ.get("AST_TOOLS_EMBEDDING_BATCH_SIZE", "16"))
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "ast-tools" / "models" / MODEL_NAME

# Global model cache (lazy-loaded)
_model: SentenceTransformer | None = None


def get_model(cache_dir: str | None = None) -> SentenceTransformer:
    """Load or return cached embedding model.

    Args:
        cache_dir: Optional custom cache directory for model weights.
                  Defaults to ~/.cache/ast-tools/models/{MODEL_NAME}/

    Returns:
        Loaded SentenceTransformer model

    Raises:
        RuntimeError: If model fails to load (with recovery instructions)

    Note:
        Model is cached globally after first load. Subsequent calls return
        the cached instance (no re-download).
    """
    global _model
    if _model is None:
        cache_path = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        cache_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Loading embedding model: {MODEL_NAME} from {cache_path}")

        try:
            _model = SentenceTransformer(MODEL_NAME, cache_folder=str(cache_path))
            logger.info(f"Model loaded successfully (dimension: {EMBEDDING_DIM})")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise RuntimeError(
                f"Failed to load embedding model '{MODEL_NAME}'. "
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
        return [0.0] * EMBEDDING_DIM

    try:
        embedding = model.encode([text], convert_to_numpy=True, normalize_embeddings=True)[0]
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return [0.0] * EMBEDDING_DIM


def generate_batch_embeddings(
    texts: list[str], model: SentenceTransformer | None = None, batch_size: int = DEFAULT_BATCH_SIZE
) -> list[list[float]]:
    """Generate embeddings for multiple texts efficiently.

    Args:
        texts: List of texts to embed
        model: Optional pre-loaded model
        batch_size: Number of texts to process in parallel (default: from AST_TOOLS_EMBEDDING_BATCH_SIZE or 16)
                   Lower = less RAM, higher = faster (but more memory)

    Returns:
        List of embeddings (same order as input texts)

    Note:
        - Batch processing is 5-10x faster than individual calls
        - RAM usage scales with batch_size (16 = ~25MB overhead, 32 = ~50MB)
        - For 4GB RAM systems, keep batch_size ≤ 64
    """
    if model is None:
        model = get_model()

    # Filter empty texts but preserve positions
    non_empty_indices = [(i, text) for i, text in enumerate(texts) if text and text.strip()]

    if not non_empty_indices:
        return [[0.0] * EMBEDDING_DIM for _ in texts]

    # Generate embeddings for non-empty texts
    non_empty_texts = [text for _, text in non_empty_indices]

    try:
        embeddings = model.encode(
            non_empty_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100,  # Only show for large batches
        )
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings: {e}")
        return [[0.0] * EMBEDDING_DIM for _ in texts]

    # Reconstruct full list with zero vectors for empty inputs
    result = [[0.0] * EMBEDDING_DIM for _ in texts]
    for (i, _), emb in zip(non_empty_indices, embeddings, strict=False):
        result[i] = emb.tolist()

    return result


def unload_model() -> None:
    """Unload model from memory (frees ~300MB RAM).

    Useful for batch operations where model is only needed temporarily.
    Call get_model() again to reload.
    """
    global _model
    if _model is not None:
        del _model
        _model = None
        logger.info("Embedding model unloaded from memory")
