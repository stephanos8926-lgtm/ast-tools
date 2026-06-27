"""KNN graph builder using hnswlib for approximate nearest neighbors.

Builds and maintains a KNN graph for semantic code search:
- Efficient similarity search (O(log N) instead of O(N²))
- Incremental updates (add new symbols without rebuild)
- Approximate search with configurable accuracy

Usage:
    builder = KNNGraphBuilder(dim=384)
    builder.add_item("symbol_id", embedding_vector)
    builder.build()
    neighbors = builder.query(query_embedding, k=10)
"""

import logging
import sqlite3
import struct

logger = logging.getLogger(__name__)

try:
    import hnswlib

    HNSWLIB_AVAILABLE = True
except ImportError:
    HNSWLIB_AVAILABLE = False
    logger.warning("hnswlib not installed - KNN search will fall back to brute force")


class KNNGraphBuilder:
    """Build and query KNN graphs using hnswlib.

    HNSW (Hierarchical Navigable Small World) provides:
    - Fast approximate nearest neighbor search
    - O(log N) query time vs O(N) for brute force
    - Incremental updates without full rebuild

    Parameters:
    - ef_construction: 200 (higher = better accuracy, slower build)
    - M: 16 (number of connections, higher = better recall, more memory)
    - ef_search: 50 (runtime search parameter, higher = better recall)
    """

    def __init__(self, dim: int = 384, space: str = "cosine"):
        """Initialize KNN graph builder.

        Args:
            dim: Embedding dimension (384 for BGE-small)
            space: Distance metric ('cosine', 'l2', or 'ip')
        """
        self.dim = dim
        self.space = space
        self._index: hnswlib.Index | None = None
        self._id_map: dict[int, str] = {}  # internal_id -> symbol_id
        self._reverse_map: dict[str, int] = {}  # symbol_id -> internal_id
        self._next_id = 0

        if not HNSWLIB_AVAILABLE:
            logger.warning("hnswlib not available - KNN queries will be brute-force")

    def add_item(self, symbol_id: str, embedding: list[float]) -> None:
        """Add a symbol to the KNN index.

        Args:
            symbol_id: Unique symbol identifier
            embedding: Embedding vector (length = dim)
        """
        if not HNSWLIB_AVAILABLE:
            # Store for later brute-force
            if not hasattr(self, "_fallback_items"):
                self._fallback_items = []
            self._fallback_items.append((symbol_id, embedding))
            self._id_map[self._next_id] = symbol_id
            self._reverse_map[symbol_id] = self._next_id
            self._next_id += 1
            return

        # Initialize index if needed
        if self._index is None:
            self._index = hnswlib.Index(space=self.space, dim=self.dim)
            self._index.init_index(max_elements=10000, ef_construction=200, M=16)

        # Initialize if needed
        if self._next_id == 0:
            self._index.init_index(max_elements=10000, ef_construction=200, M=16)

        # Resize if needed
        if self._next_id >= self._index.get_max_elements():
            new_size = self._index.get_max_elements() * 2
            self._index.resize_index(new_size)

        # Add to index
        self._index.add_items([embedding], [self._next_id])

        # Update maps
        self._id_map[self._next_id] = symbol_id
        self._reverse_map[symbol_id] = self._next_id
        self._next_id += 1

        logger.debug(f"Added {symbol_id} to KNN index (size={self._next_id})")

    def build(self) -> None:
        """Finalize the index for querying.

        Optional: call after adding all items for optimal performance.
        """
        if self._index is not None:
            self._index.set_ef(50)  # Search parameter
            logger.info(f"Built KNN index with {self._next_id} items")

    def query(self, query_embedding: list[float], k: int = 10) -> list[tuple[str, float]]:
        """Find k nearest neighbors for a query embedding.

        Args:
            query_embedding: Query vector
            k: Number of neighbors to return

        Returns:
            List of (symbol_id, similarity_score) tuples
        """
        if not HNSWLIB_AVAILABLE or self._index is None:
            return self._brute_force_query(query_embedding, k)

        # Query index
        labels, distances = self._index.knn_query([query_embedding], k=k)

        # Convert to (symbol_id, similarity) format
        results = []
        for label, dist in zip(labels[0], distances[0], strict=False):
            symbol_id = self._id_map.get(label)
            if symbol_id:
                # Convert distance to similarity (cosine: 1-dist = sim)
                similarity = 1.0 - dist if self.space == "cosine" else 1.0 / (1.0 + dist)
                results.append((symbol_id, similarity))

        return results

    def _brute_force_query(self, query_embedding: list[float], k: int) -> list[tuple[str, float]]:
        """Fallback brute-force KNN search.

        O(N) complexity - use only for small datasets or testing.
        """
        if not hasattr(self, "_fallback_items"):
            return []

        # Compute cosine similarity for all items
        similarities = []
        for symbol_id, embedding in self._fallback_items:
            sim = self._cosine_similarity(query_embedding, embedding)
            similarities.append((symbol_id, sim))

        # Sort and return top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def save_index(self, path: str) -> None:
        """Save index to disk.

        Args:
            path: File path to save index
        """
        if self._index is not None:
            self._index.save_index(path)
            logger.info(f"Saved KNN index to {path}")

    def load_index(self, path: str) -> None:
        """Load index from disk.

        Args:
            path: File path to load index
        """
        if HNSWLIB_AVAILABLE:
            self._index = hnswlib.Index(space=self.space, dim=self.dim)
            self._index.load_index(path)
            logger.info(f"Loaded KNN index from {path}")

    def get_item_count(self) -> int:
        """Get number of items in index."""
        return self._next_id


def build_knn_graph_from_db(conn: sqlite3.Connection, dim: int = 384) -> KNNGraphBuilder:
    """Build KNN graph from embedding table in database.

    Usage:
        knn = build_knn_graph_from_db(db_conn)
        neighbors = knn.query(query_embedding, k=10)

    Args:
        conn: SQLite connection
        dim: Embedding dimension

    Returns:
        Built KNNGraphBuilder
    """
    builder = KNNGraphBuilder(dim=dim)

    # Load embeddings from database
    # Note: Assumes embeddings stored in a table with (symbol_id, embedding) columns
    # Phase 2 implementation detail - may need adjustment
    cursor = conn.execute("""
        SELECT symbol_id, embedding
        FROM symbol_embeddings
        WHERE embedding IS NOT NULL
    """)

    count = 0
    for symbol_id, embedding_blob in cursor.fetchall():
        if embedding_blob:
            # Deserialize embedding (assumes stored as blob of floats)
            embedding = list(struct.unpack(f"{len(embedding_blob) // 4}f", embedding_blob))
            builder.add_item(symbol_id, embedding)
            count += 1

    builder.build()
    logger.info(f"Built KNN graph with {count} embeddings")

    return builder


def store_similarity_to_db(
    conn: sqlite3.Connection,
    symbol_id_1: str,
    symbol_id_2: str,
    similarity: float,
    model_version: str = "BGE-small-en-v1.5",
) -> None:
    """Store pairwise similarity to database.

    Stores only top similarities to avoid O(N²) storage.

    Args:
        conn: SQLite connection
        symbol_id_1: First symbol
        symbol_id_2: Second symbol
        similarity: Cosine similarity (-1 to 1)
        model_version: Embedding model version
    """
    # Normalize IDs (smaller first for consistency)
    if symbol_id_1 > symbol_id_2:
        symbol_id_1, symbol_id_2 = symbol_id_2, symbol_id_1

    conn.execute(
        """
        INSERT OR REPLACE INTO embedding_similarity
        (symbol_id_1, symbol_id_2, cosine_similarity, embedding_model_version, is_stale)
        VALUES (?, ?, ?, ?, 0)
    """,
        (symbol_id_1, symbol_id_2, similarity, model_version),
    )


def store_knn_to_db(
    conn: sqlite3.Connection,
    symbol_id: str,
    neighbors: list[tuple[str, float]],
    min_similarity: float = 0.7,
) -> int:
    """Store KNN neighbors to database.

    Filters by minimum similarity threshold.

    Args:
        conn: SQLite connection
        symbol_id: Source symbol
        neighbors: List of (neighbor_id, similarity)
        min_similarity: Minimum similarity threshold

    Returns:
        Number of neighbors stored
    """
    count = 0
    with conn:
        for neighbor_id, similarity in neighbors:
            if similarity >= min_similarity:
                store_similarity_to_db(conn, symbol_id, neighbor_id, similarity)
                count += 1

    return count
