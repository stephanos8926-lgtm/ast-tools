"""Tests for embeddings store (sqlite-vec integration)."""

import sqlite3

import pytest

from ast_tools.embeddings.store import (
    EMBEDDING_DIM,
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


pytestmark = pytest.mark.slow

@pytest.fixture
def vec_conn():
    """Create an in-memory SQLite connection with sqlite-vec loaded."""
    conn = sqlite3.connect(":memory:")
    load_vec_extension(conn)

    # Create the symbols_vec virtual table
    conn.execute("""
        CREATE VIRTUAL TABLE symbols_vec USING vec0(
            symbol_id TEXT PRIMARY KEY,
            embedding FLOAT[384]
        )
    """)

    # Also create a symbols table for testing file-based operations
    conn.execute("""
        CREATE TABLE symbols (
            id TEXT PRIMARY KEY,
            name TEXT,
            file_path TEXT
        )
    """)

    conn.commit()
    yield conn
    conn.close()


class TestFloatConversion:
    """Test float<->bytes conversion utilities."""

    def test_floats_to_bytes_roundtrip(self):
        """floats->bytes->floats should preserve values (within float32 precision)."""
        floats = [0.1, 0.5, 0.9, -0.5, 0.0]
        bytes_data = _floats_to_bytes(floats)
        converted_back = _bytes_to_floats(bytes_data)
        # Float32 has limited precision, so check approximate equality
        for orig, conv in zip(floats, converted_back, strict=False):
            assert abs(orig - conv) < 1e-6, f"{orig} != {conv}"

    def test_floats_to_bytes_preserves_length(self):
        """Length of floats should match length of converted bytes/4."""
        floats = list(range(384))
        bytes_data = _floats_to_bytes(floats)
        assert len(bytes_data) / 4 == len(floats)

    def test_empty_list_conversion(self):
        """Empty list should convert to empty bytes."""
        float_bytes = _floats_to_bytes([])
        assert float_bytes == b""
        assert _bytes_to_floats(b"") == []


class TestInsertEmbedding:
    """Test single embedding insertion."""

    def test_insert_embedding_success(self, vec_conn):
        """insert_embedding() should successfully insert."""
        embedding = [0.1] * EMBEDDING_DIM
        insert_embedding(vec_conn, "test_sym", embedding)

        # Verify count increased
        assert get_embedding_count(vec_conn) == 1

    def test_insert_embedding_dimension_check(self, vec_conn):
        """insert_embedding() should reject wrong dimensions."""
        wrong_emb = [0.1] * 100  # Wrong dimension
        with pytest.raises(ValueError, match="384"):
            insert_embedding(vec_conn, "bad", wrong_emb)

    def test_insert_embedding_replaces_existing(self, vec_conn):
        """insert_embedding() should replace existing embeddings."""
        emb1 = [0.1] * EMBEDDING_DIM
        emb2 = [0.2] * EMBEDDING_DIM

        insert_embedding(vec_conn, "sym", emb1)
        insert_embedding(vec_conn, "sym", emb2)

        result = search_similar(vec_conn, emb2, k=5)
        assert len(result) == 1
        assert result[0][0] == "sym"


class TestInsertEmbeddingsBatch:
    """Test batch embedding insertion."""

    def test_batch_insert_success(self, vec_conn):
        """insert_embeddings_batch() should insert multiple."""
        embeddings = [
            ("sym1", [0.1] * EMBEDDING_DIM),
            ("sym2", [0.2] * EMBEDDING_DIM),
            ("sym3", [0.3] * EMBEDDING_DIM),
        ]
        insert_embeddings_batch(vec_conn, embeddings)

        assert get_embedding_count(vec_conn) == 3

    def test_batch_insert_empty(self, vec_conn):
        """Empty batch should do nothing."""
        insert_embeddings_batch(vec_conn, [])
        assert get_embedding_count(vec_conn) == 0

    def test_batch_insert_replaces(self, vec_conn):
        """Batch should replace existing embeddings."""
        batch1 = [("sym", [0.1] * EMBEDDING_DIM)]
        batch2 = [("sym", [0.9] * EMBEDDING_DIM)]

        insert_embeddings_batch(vec_conn, batch1)
        insert_embeddings_batch(vec_conn, batch2)

        result = search_similar(vec_conn, [0.9] * EMBEDDING_DIM, k=5)
        assert result[0][0] == "sym"


class TestSearchSimilar:
    """Test similarity search."""

    def test_search_returns_results(self, vec_conn):
        """search_similar() should return matching embeddings."""
        emb = [0.1] * EMBEDDING_DIM
        insert_embedding(vec_conn, "test_sym", emb)

        results = search_similar(vec_conn, emb, k=5)
        assert len(results) == 1
        assert results[0][0] == "test_sym"

    def test_search_ranking(self, vec_conn):
        """Search should return results ordered by distance."""
        base_emb = [0.1] * EMBEDDING_DIM

        insert_embedding(vec_conn, "exact", base_emb)
        insert_embedding(vec_conn, "close", [0.15] * EMBEDDING_DIM)
        insert_embedding(vec_conn, "far", [0.9] * EMBEDDING_DIM)

        results = search_similar(vec_conn, base_emb, k=10)

        assert len(results) == 3
        assert results[0][0] == "exact"  # Should be closest

    def test_search_respects_limit(self, vec_conn):
        """search_similar() should respect k parameter."""
        for i in range(10):
            emb = [0.1 + i * 0.01] * EMBEDDING_DIM
            insert_embedding(vec_conn, f"sym{i}", emb)

        results = search_similar(vec_conn, [0.1] * EMBEDDING_DIM, k=3)
        assert len(results) == 3

    def test_search_dimension_check(self, vec_conn):
        """search_similar() should reject wrong dimensions."""
        wrong_emb = [0.1] * 100  # Wrong dimension
        with pytest.raises(ValueError, match="384"):
            search_similar(vec_conn, wrong_emb, k=5)


class TestGetEmbeddingCount:
    """Test embedding count retrieval."""

    def test_count_empty(self, vec_conn):
        """get_embedding_count() should return 0 for empty table."""
        assert get_embedding_count(vec_conn) == 0

    def test_count_increases_after_insert(self, vec_conn):
        """Count should increase after insert."""
        insert_embedding(vec_conn, "sym1", [0.1] * EMBEDDING_DIM)
        assert get_embedding_count(vec_conn) == 1

        insert_embedding(vec_conn, "sym2", [0.2] * EMBEDDING_DIM)
        assert get_embedding_count(vec_conn) == 2


class TestGetSymbolsWithoutEmbeddings:
    """Test finding symbols needing embeddings."""

    def test_finds_symbols_without_embeddings(self, vec_conn):
        """Should return symbols that don't have embeddings."""
        vec_conn.execute("INSERT INTO symbols (id, name, file_path) VALUES ('s1', 'test1', 'f.py')")
        vec_conn.execute("INSERT INTO symbols (id, name, file_path) VALUES ('s2', 'test2', 'f.py')")
        vec_conn.commit()

        insert_embedding(vec_conn, "s1", [0.1] * EMBEDDING_DIM)

        without_emb = get_symbols_without_embeddings(vec_conn)
        assert without_emb == ["s2"]

    def test_returns_empty_when_all_have_embeddings(self, vec_conn):
        """Should return empty list when all have embeddings."""
        vec_conn.execute("INSERT INTO symbols (id, name, file_path) VALUES ('s1', 'test', 'f.py')")
        vec_conn.commit()

        insert_embedding(vec_conn, "s1", [0.1] * EMBEDDING_DIM)

        without_emb = get_symbols_without_embeddings(vec_conn)
        assert without_emb == []


class TestDeleteEmbedding:
    """Test embedding deletion."""

    def test_delete_single_embedding(self, vec_conn):
        """delete_embedding() should remove one embedding."""
        insert_embedding(vec_conn, "test", [0.1] * EMBEDDING_DIM)
        assert get_embedding_count(vec_conn) == 1

        delete_embedding(vec_conn, "test")
        assert get_embedding_count(vec_conn) == 0

    def test_delete_nonexistent_embedding(self, vec_conn):
        """Deleting non-existent embedding should not error."""
        delete_embedding(vec_conn, "nonexistent")  # Should not raise


class TestDeleteEmbeddingsForFile:
    """Test file-based embedding deletion."""

    def test_delete_all_for_file(self, vec_conn):
        """delete_embeddings_for_file() should remove all for that file."""
        vec_conn.execute("INSERT INTO symbols (id, name, file_path) VALUES ('s1', 'a', 'file1.py')")
        vec_conn.execute("INSERT INTO symbols (id, name, file_path) VALUES ('s2', 'b', 'file1.py')")
        vec_conn.execute("INSERT INTO symbols (id, name, file_path) VALUES ('s3', 'c', 'file2.py')")
        vec_conn.commit()

        for sym_id in ["s1", "s2", "s3"]:
            insert_embedding(vec_conn, sym_id, [0.1] * EMBEDDING_DIM)

        assert get_embedding_count(vec_conn) == 3

        # Delete embeddings for file1.py
        deleted = delete_embeddings_for_file(vec_conn, "file1.py")
        assert deleted == 2
        assert get_embedding_count(vec_conn) == 1

        # s3 should still have embedding
        result = search_similar(vec_conn, [0.1] * EMBEDDING_DIM, k=5)
        assert result[0][0] == "s3"
