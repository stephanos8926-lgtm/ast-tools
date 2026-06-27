"""Embeddings layer for semantic code search.

Provides transformer-based embedding generation and vector storage/search via sqlite-vec.
"""

from .model import (
    EMBEDDING_DIM,
    MODEL_NAME,
    generate_batch_embeddings,
    generate_embedding,
    get_model,
    unload_model,
)
from .store import (
    _bytes_to_floats,
    _floats_to_bytes,
    delete_embedding,
    delete_embeddings_for_file,
    get_embedding_count,
    get_symbols_without_embeddings,
    insert_embedding,
    insert_embeddings_batch,
    load_vec_extension,
    search_similar,
)

# Prefer model.py's EMBEDDING_DIM if both are imported
__all__ = [
    "EMBEDDING_DIM",
    "MODEL_NAME",
    "_bytes_to_floats",
    "_floats_to_bytes",
    "delete_embedding",
    "delete_embeddings_for_file",
    "generate_batch_embeddings",
    "generate_embedding",
    "get_embedding_count",
    "get_model",
    "get_symbols_without_embeddings",
    "insert_embedding",
    "insert_embeddings_batch",
    "load_vec_extension",
    "search_similar",
    "unload_model",
]
