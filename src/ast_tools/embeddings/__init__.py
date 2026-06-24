"""Embeddings layer for semantic code search.

Provides transformer-based embedding generation and vector storage/search via sqlite-vec.
"""

from .model import (
    get_model,
    generate_embedding,
    generate_batch_embeddings,
    MODEL_NAME,
    EMBEDDING_DIM,
    unload_model,
)
from .store import (
    load_vec_extension,
    insert_embedding,
    insert_embeddings_batch,
    search_similar,
    get_embedding_count,
    get_symbols_without_embeddings,
    delete_embedding,
    delete_embeddings_for_file,
    _floats_to_bytes,
    _bytes_to_floats,
)

# Prefer model.py's EMBEDDING_DIM if both are imported
__all__ = [
    'get_model',
    'generate_embedding',
    'generate_batch_embeddings',
    'unload_model',
    'insert_embedding',
    'insert_embeddings_batch',
    'search_similar',
    'MODEL_NAME',
    'EMBEDDING_DIM',
    'load_vec_extension',
    'get_embedding_count',
    'get_symbols_without_embeddings',
    'delete_embedding',
    'delete_embeddings_for_file',
    '_floats_to_bytes',
    '_bytes_to_floats',
]