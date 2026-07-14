"""Embeddings layer for semantic code search.

Provides transformer-based embedding generation and vector storage/search via sqlite-vec.
Supports both local (sentence-transformers) and remote (RW_InferenceEngine) backends.
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
from .provider import (
    EmbeddingBackend,
    EmbeddingProvider,
    generate_batch_embeddings as provider_generate_batch_embeddings,
    generate_embedding as provider_generate_embedding,
    get_embedding_provider,
)
from .remote_inference import (
    RemoteInferenceClient,
    RemoteInferenceConfig,
)
from .model_registry import (
    EmbeddingModelConfig,
    EmbeddingModelProvider,
    EmbeddingModelRegistry,
    ModelRegistryState,
    DEFAULT_MODELS,
    get_model_registry,
    close_model_registry,
)

# Prefer model.py's EMBEDDING_DIM if both are imported
__all__ = [
    "EMBEDDING_DIM",
    "MODEL_NAME",
    "EmbeddingBackend",
    "EmbeddingProvider",
    "EmbeddingModelConfig",
    "EmbeddingModelProvider",
    "EmbeddingModelRegistry",
    "ModelRegistryState",
    "DEFAULT_MODELS",
    "RemoteInferenceClient",
    "RemoteInferenceConfig",
    "_bytes_to_floats",
    "_floats_to_bytes",
    "delete_embedding",
    "delete_embeddings_for_file",
    "generate_batch_embeddings",
    "generate_embedding",
    "get_embedding_count",
    "get_embedding_provider",
    "get_model",
    "get_model_registry",
    "close_model_registry",
    "get_symbols_without_embeddings",
    "insert_embedding",
    "insert_embeddings_batch",
    "load_vec_extension",
    "search_similar",
    "unload_model",
]