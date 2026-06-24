"""Context Injector - Relevance Scoring, Budget Management, Selection."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import math
import numpy as np

from .history import InjectionHistory


@dataclass
class Symbol:
    """Symbol representation for context injection."""
    
    id: str
    name: str
    kind: str
    file_path: str
    line: int
    signature: str
    docstring: Optional[str]
    embedding: Optional[np.ndarray]
    references_count: int
    last_indexed: str


# ============================================================================
# Helper functions
# ============================================================================

def calculate_recency_score(last_indexed: datetime) -> float:
    """Calculate recency score using exponential decay.
    
    Half-life: 30 days. Minimum score: 0.01.
    """
    days_since = (datetime.now() - last_indexed).days
    if days_since <= 0:
        return 1.0
    
    decay = math.exp(-days_since / 30.0)
    return max(0.01, min(1.0, decay))


def calculate_usage_score(ref_count: int, max_refs: int = 100) -> float:
    """Calculate usage frequency score using log scaling.
    
    Avoids domination by heavily-referenced symbols.
    """
    max_refs = max(1, max_refs)  # Prevent division by zero
    return math.log1p(ref_count) / math.log1p(max_refs)


def calculate_kind_boost(kind: str) -> float:
    """Calculate kind-based score boost.
    
    Classes/functions are more useful than variables for context.
    """
    boosts = {
        'class': 1.0,
        'function': 1.0,
        'method': 0.8,
        'constant': 0.7,
        'variable': 0.4,
        'alias': 0.5,
        'module': 0.6
    }
    return boosts.get(kind.lower(), 0.5)


def calculate_proximity_score(
    symbol_file: str,
    current_file: Optional[str]
) -> float:
    """Calculate file proximity score.
    
    Same file = 1.0, imported file = 0.5, unrelated = 0.0
    """
    if not current_file:
        return 0.5  # Default if current file unknown
    
    if symbol_file == current_file:
        return 1.0
    
    # Check if in same directory
    from pathlib import Path
    symbol_dir = Path(symbol_file).parent
    current_dir = Path(current_file).parent
    
    if symbol_dir == current_dir:
        return 0.7
    
    # Check if in project (assume /src/ or project root)
    if 'src' in symbol_file and 'src' in current_file:
        return 0.5
    
    return 0.2


# ============================================================================
# ContextInjector class (continued from part1)
# ============================================================================

class ContextInjector:
    """Manages context injection for ast-tools MCP server."""
    
    DEFAULT_WEIGHTS = {
        'semantic': 0.40,
        'recency': 0.15,
        'usage': 0.15,
        'kind': 0.10,
        'proximity': 0.10,
        'callgraph': 0.10
    }
    
    def __init__(
        self,
        db_path: Path,
        model_context_window: int = 32000,
        max_context_symbols: int = 10,
        diversity_limit: int = 3,
        protect_last_n_messages: int = 2,
        weights: Optional[Dict[str, float]] = None
    ):
        """Initialize context injector."""
        self.db_path = db_path
        self.model_context_window = model_context_window
        self.max_context_symbols = max_context_symbols
        self.diversity_limit = diversity_limit
        self.protect_last_n_messages = protect_last_n_messages
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        
        self.history = InjectionHistory(session_id="current")
        
        # Validate weights
        total_weight = sum(self.weights.values())
        if not 0.95 <= total_weight <= 1.05:
            raise ValueError(f"Relevance weights must sum to 1.0, got {total_weight}")
    
    def calculate_relevance_score(
        self,
        symbol: Any,
        query_embedding: Optional[np.ndarray] = None,
        current_file: Optional[str] = None
    ) -> float:
        """Calculate multi-factor relevance score."""
        # Semantic similarity (40%)
        semantic_score = 0.0
        if query_embedding is not None and hasattr(symbol, 'embedding') and symbol.embedding is not None:
            try:
                semantic_score = self._calculate_semantic_similarity(
                    query_embedding, symbol.embedding
                )
            except Exception:
                semantic_score = 0.0
        
        # Recency score (15%)
        recency_score = 0.5
        try:
            if hasattr(symbol, 'last_indexed'):
                last_indexed = datetime.fromisoformat(symbol.last_indexed)
                recency_score = calculate_recency_score(last_indexed)
        except Exception:
            pass
        
        # Usage frequency (15%)
        usage_score = 0.5
        try:
            if hasattr(symbol, 'references_count'):
                usage_score = calculate_usage_score(symbol.references_count)
        except Exception:
            pass
        
        # Kind boost (10%)
        kind_score = 0.5
        try:
            if hasattr(symbol, 'kind'):
                kind_score = calculate_kind_boost(symbol.kind)
        except Exception:
            pass
        
        # File proximity (10%)
        proximity_score = 0.5
        try:
            if hasattr(symbol, 'file_path'):
                proximity_score = calculate_proximity_score(symbol.file_path, current_file)
        except Exception:
            pass
        
        # Callgraph depth (10%) - placeholder
        callgraph_score = 0.5
        
        # Combine scores
        total_score = (
            semantic_score * self.weights['semantic'] +
            recency_score * self.weights['recency'] +
            usage_score * self.weights['usage'] +
            kind_score * self.weights['kind'] +
            proximity_score * self.weights['proximity'] +
            callgraph_score * self.weights['callgraph']
        )
        
        # Apply history-based modifier
        if hasattr(symbol, 'id'):
            history_modifier = self.history.get_injection_score_modifier(symbol.id)
            total_score *= history_modifier
        
        return min(1.0, max(0.0, total_score))
    
    def _calculate_semantic_similarity(
        self,
        query_emb: np.ndarray,
        symbol_emb: np.ndarray
    ) -> float:
        """Calculate cosine similarity between embeddings."""
        query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-10)
        symbol_norm = symbol_emb / (np.linalg.norm(symbol_emb) + 1e-10)
        similarity = float(np.dot(query_norm, symbol_norm))
        return (similarity + 1.0) / 2.0

    # Wrapper methods for test compatibility
    def _calculate_recency_score(self, last_indexed: datetime) -> float:
        return calculate_recency_score(last_indexed)

    def _calculate_usage_score(self, ref_count: int, max_refs: int = 100) -> float:
        return calculate_usage_score(ref_count, max_refs)

    def _calculate_kind_boost(self, kind: str) -> float:
        return calculate_kind_boost(kind)

    def _calculate_proximity_score(self, symbol_file: str, current_file: Optional[str] = None) -> float:
        return calculate_proximity_score(symbol_file, current_file)

    def estimate_symbol_tokens(self, symbol: Any) -> int:
        """Estimate token count for a symbol.
        
        Rough estimate: 1 symbol ≈ 300 tokens (signature + docstring + context)
        """
        base = 150  # Base overhead
        
        # Add for signature length
        if hasattr(symbol, 'signature'):
            base += len(str(symbol.signature)) // 4
        
        # Add for docstring
        if hasattr(symbol, 'docstring') and symbol.docstring:
            base += len(str(symbol.docstring)) // 4
        
        return min(base, 1000)  # Cap at 1000 tokens
    
    def calculate_available_budget(self, existing_context_tokens: int = 0) -> int:
        """Calculate available token budget for context injection.
        
        Reserves space for protected messages.
        """
        # Estimate protected message tokens
        protected_tokens = self.protect_last_n_messages * 500
        
        available = (
            self.model_context_window
            - existing_context_tokens
            - protected_tokens
        )
        
        return max(0, available)
    
    def select_top_k(
        self,
        symbols: List[Dict],
        k: Optional[int] = None
    ) -> List[Dict]:
        """Select top-k symbols with diversity enforcement.
        
        Args:
            symbols: List of Symbol dataclasses with relevance_score attribute
            k: Number to select (uses max_context_symbols if None)
            
        Returns:
            Selected symbols respecting diversity limit
        """
        k = k or self.max_context_symbols
        
        # Sort by relevance score (descending)
        sorted_symbols = sorted(
            symbols,
            key=lambda s: getattr(s, 'relevance_score', 0.0),
            reverse=True
        )
        
        # Enforce diversity
        return self.history.enforce_diversity(
            sorted_symbols,
            limit=self.diversity_limit
        )[:k]