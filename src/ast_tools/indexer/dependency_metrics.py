"""Calculates dependency metrics for code symbols.

Metrics:
- fan_in: Number of symbols that depend on this symbol
- fan_out: Number of symbols this symbol depends on
- spof_score: Single Point of Failure score (0-1)
- instability: Ratio of outgoing to total dependencies
- centrality: PageRank-based importance score

Usage:
    calculator = DependencyMetricsCalculator()
    calculator.add_edge("A", "B")  # A depends on B
    metrics = calculator.compute_all()
"""

import sqlite3
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import logging
import math

logger = logging.getLogger(__name__)


class DependencyMetricsCalculator:
    """Calculate dependency metrics from edge data.
    
    Computes architectural intelligence metrics:
    - Fan-in/fan-out counts
    - SPOF (Single Point of Failure) score
    - Instability (I = Ce / (Ca + Ce))
    - PageRank centrality
    """
    
    def __init__(self):
        """Initialize calculator."""
        self._dependents: Dict[str, Set[str]] = defaultdict(set)  # symbol -> who depends on it
        self._dependencies: Dict[str, Set[str]] = defaultdict(set)  # symbol -> what it depends on
        self._all_symbols: Set[str] = set()
    
    def add_edge(self, source_id: str, target_id: str) -> None:
        """Record a dependency edge.
        
        Args:
            source_id: Symbol that has the dependency (caller)
            target_id: Symbol being depended on (callee)
        """
        self._dependents[target_id].add(source_id)
        self._dependencies[source_id].add(target_id)
        self._all_symbols.add(source_id)
        self._all_symbols.add(target_id)
    
    def compute_fan_in(self, symbol_id: str) -> int:
        """Compute fan-in (afferent couplings).
        
        Fan-in is the number of symbols that depend on this symbol.
        High fan-in = widely used, potentially critical.
        
        Args:
            symbol_id: Symbol to compute for
        
        Returns:
            Count of dependents
        """
        return len(self._dependents.get(symbol_id, set()))
    
    def compute_fan_out(self, symbol_id: str) -> int:
        """Compute fan-out (efferent couplings).
        
        Fan-out is the number of symbols this symbol depends on.
        High fan-out = potentially unstable, many dependencies.
        
        Args:
            symbol_id: Symbol to compute for
        
        Returns:
            Count of dependencies
        """
        return len(self._dependencies.get(symbol_id, set()))
    
    def compute_instability(self, symbol_id: str) -> float:
        """Compute instability metric.
        
        Instability I = Ce / (Ca + Ce)
        Where:
        - Ca = afferent couplings (fan-in)
        - Ce = efferent couplings (fan-out)
        
        Range: 0.0 (stable) to 1.0 (unstable)
        
        Args:
            symbol_id: Symbol to compute for
        
        Returns:
            Instability score (0-1)
        """
        fan_in = self.compute_fan_in(symbol_id)
        fan_out = self.compute_fan_out(symbol_id)
        
        total = fan_in + fan_out
        if total == 0:
            return 0.0  # No dependencies = neutral
        
        return fan_out / total
    
    def compute_spof_score(self, symbol_id: str) -> float:
        """Compute Single Point of Failure score.
        
        SPOF score combines:
        - High fan-in (many dependents)
        - Low redundancy (few alternative implementations)
        - Critical position in dependency graph
        
        Formula: SPOF = log(fan_in + 1) * (1 - instability)
        Range: 0.0 (not critical) to ~1.0 (critical SPOF)
        
        Args:
            symbol_id: Symbol to compute for
        
        Returns:
            SPOF score (0-1, normalized)
        """
        fan_in = self.compute_fan_in(symbol_id)
        instability = self.compute_instability(symbol_id)
        
        # Log scale to prevent extremely high scores
        raw_score = math.log(fan_in + 1) * (1 - instability)
        
        # Normalize to 0-1 range (log(100) ≈ 4.6 is reasonable max)
        max_score = math.log(100)
        normalized = min(1.0, raw_score / max_score)
        
        return normalized
    
    def compute_pagerank(self, damping: float = 0.85, iterations: int = 20) -> Dict[str, float]:
        """Compute PageRank centrality for all symbols.
        
        Adapted from web PageRank: symbols are "pages", dependencies are "links".
        A symbol is important if important symbols depend on it.
        
        Args:
            damping: Damping factor (0.85 is standard)
            iterations: Number of iterations
        
        Returns:
            Dict mapping symbol_id -> PageRank score
        """
        n = len(self._all_symbols)
        if n == 0:
            return {}
        
        # Initialize scores uniformly
        scores: Dict[str, float] = {s: 1.0 / n for s in self._all_symbols}
        
        for _ in range(iterations):
            new_scores: Dict[str, float] = {}
            
            for symbol in self._all_symbols:
                # Base score from damping
                score = (1 - damping) / n
                
                # Add contributions from dependents
                for dependent in self._dependents.get(symbol, set()):
                    out_count = len(self._dependencies.get(dependent, set()))
                    if out_count > 0:
                        score += damping * scores[dependent] / out_count
                
                new_scores[symbol] = score
            
            scores = new_scores
        
        # Normalize to 0-1 range
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {k: v / max_score for k, v in scores.items()}
        
        return scores
    
    def compute_all_metrics(self) -> Dict[str, dict]:
        """Compute all metrics for all symbols.
        
        Returns:
            Dict mapping symbol_id -> {
                fan_in: int,
                fan_out: int,
                spof_score: float,
                instability: float,
                centrality: float
            }
        """
        pagerank = self.compute_pagerank()
        metrics: Dict[str, dict] = {}
        
        for symbol in self._all_symbols:
            metrics[symbol] = {
                'fan_in': self.compute_fan_in(symbol),
                'fan_out': self.compute_fan_out(symbol),
                'spof_score': self.compute_spof_score(symbol),
                'instability': self.compute_instability(symbol),
                'centrality': pagerank.get(symbol, 0.0)
            }
        
        return metrics
    
    def load_from_edges(self, edges: List[Tuple[str, str]]) -> None:
        """Load edges from list of (source_id, target_id) tuples.
        
        Args:
            edges: List of (source, target) pairs
        """
        for source, target in edges:
            self.add_edge(source, target)
    
    def load_from_database(self, conn: sqlite3.Connection) -> None:
        """Load edges from database edges table.
        
        Args:
            conn: SQLite connection
        """
        cursor = conn.execute("""
            SELECT source_id, target_id 
            FROM edges 
            WHERE target_id IS NOT NULL
        """)
        
        for source_id, target_id in cursor.fetchall():
            self.add_edge(source_id, target_id)
        
        logger.info(f"Loaded {len(self._all_symbols)} symbols from database")


def compute_metrics_for_symbols(conn: sqlite3.Connection) -> Dict[str, dict]:
    """Convenience function to compute metrics from database.
    
    Usage:
        metrics = compute_metrics_for_symbols(db_conn)
        for symbol_id, m in metrics.items():
            print(f"{symbol_id}: fan_in={m['fan_in']}, centrality={m['centrality']}")
    
    Args:
        conn: SQLite connection
    
    Returns:
        Dict mapping symbol_id -> metrics dict
    """
    calculator = DependencyMetricsCalculator()
    calculator.load_from_database(conn)
    return calculator.compute_all_metrics()


def insert_metrics_to_db(
    conn: sqlite3.Connection,
    metrics: Dict[str, dict]
) -> int:
    """Insert computed metrics into dependency_metrics table.
    
    Args:
        conn: SQLite connection
        metrics: Dict from compute_all_metrics()
    
    Returns:
        Number of rows inserted
    """
    count = 0
    with conn:
        for symbol_id, m in metrics.items():
            conn.execute("""
                INSERT OR REPLACE INTO dependency_metrics 
                (symbol_id, fan_in, fan_out, spof_score, instability, centrality)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                symbol_id,
                m['fan_in'],
                m['fan_out'],
                round(m['spof_score'], 4),
                round(m['instability'], 4),
                round(m['centrality'], 4)
            ))
            count += 1
    
    logger.info(f"Inserted {count} dependency metrics")
    return count