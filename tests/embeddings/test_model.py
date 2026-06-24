"""Tests for embeddings model."""

from ast_tools.embeddings import (
    get_model,
    generate_embedding,
    generate_batch_embeddings,
    MODEL_NAME,
    EMBEDDING_DIM,
    unload_model,
)


class TestModelLoading:
    """Test model loading and caching."""
    
    def test_model_name_constant(self):
        """MODEL_NAME should be set to all-MiniLM-L6-v2."""
        assert MODEL_NAME == "all-MiniLM-L6-v2"
    
    def test_embedding_dim_constant(self):
        """EMBEDDING_DIM should be 384."""
        assert EMBEDDING_DIM == 384
    
    def test_get_model_returns_model(self):
        """get_model() should return a SentenceTransformer instance."""
        model = get_model()
        assert model is not None
        assert hasattr(model, 'encode')
    
    def test_get_model_caches_globally(self):
        """get_model() should return the same instance on subsequent calls."""
        model1 = get_model()
        model2 = get_model()
        assert model1 is model2
    
    def test_unload_model_clears_cache(self):
        """unload_model() should clear the global cache."""
        model1 = get_model()
        unload_model()
        model2 = get_model()
        assert model1 is not model2


class TestGenerateEmbedding:
    """Test single embedding generation."""
    
    def test_generate_embedding_returns_list(self):
        """generate_embedding() should return a list of floats."""
        embedding = generate_embedding("test function")
        assert isinstance(embedding, list)
        assert len(embedding) == EMBEDDING_DIM
        assert all(isinstance(x, float) for x in embedding)
    
    def test_generate_embedding_empty_string(self):
        """Empty string should return zero vector."""
        embedding = generate_embedding("")
        assert embedding == [0.0] * EMBEDDING_DIM
    
    def test_generate_embedding_whitespace_only(self):
        """Whitespace-only string should return zero vector."""
        embedding = generate_embedding("   \n\t  ")
        assert embedding == [0.0] * EMBEDDING_DIM
    
    def test_generate_embedding_normalizes(self):
        """Embeddings should be normalized (L2 norm = 1.0)."""
        import math
        embedding = generate_embedding("test function")
        norm = math.sqrt(sum(x*x for x in embedding))
        assert abs(norm - 1.0) < 0.01  # Should be normalized


class TestGenerateBatchEmbeddings:
    """Test batch embedding generation."""
    
    def test_batch_embeddings_returns_list(self):
        """generate_batch_embeddings() should return list of embeddings."""
        texts = ["function one", "function two", "function three"]
        embeddings = generate_batch_embeddings(texts)
        assert isinstance(embeddings, list)
        assert len(embeddings) == 3
        assert all(len(e) == EMBEDDING_DIM for e in embeddings)
    
    def test_batch_embeddings_empty_list(self):
        """Empty list should return empty list."""
        embeddings = generate_batch_embeddings([])
        assert embeddings == []
    
    def test_batch_embeddings_preserves_order(self):
        """Embeddings should preserve input order."""
        texts = ["a", "b", "c"]
        embeddings = generate_batch_embeddings(texts)
        # All should be different (different texts)
        assert embeddings[0] != embeddings[1]
        assert embeddings[1] != embeddings[2]
    
    def test_batch_embeddings_handles_empty_strings(self):
        """Empty strings in batch should return zero vectors."""
        texts = ["real text", "", "more text"]
        embeddings = generate_batch_embeddings(texts)
        assert embeddings[0] != [0.0] * EMBEDDING_DIM
        assert embeddings[1] == [0.0] * EMBEDDING_DIM
        assert embeddings[2] != [0.0] * EMBEDDING_DIM
    
    def test_batch_embeddings_batch_size_parameter(self):
        """batch_size parameter should be accepted."""
        texts = ["a", "b", "c", "d", "e"]
        embeddings = generate_batch_embeddings(texts, batch_size=2)
        assert len(embeddings) == 5
        assert all(len(e) == EMBEDDING_DIM for e in embeddings)


class TestModelConfiguration:
    """Test model configuration constants."""
    
    def test_model_name_is_public(self):
        """MODEL_NAME should be a public constant."""
        assert isinstance(MODEL_NAME, str)
        assert len(MODEL_NAME) > 0
    
    def test_embedding_dim_is_public(self):
        """EMBEDDING_DIM should be a public constant."""
        assert isinstance(EMBEDDING_DIM, int)
        assert EMBEDDING_DIM == 384