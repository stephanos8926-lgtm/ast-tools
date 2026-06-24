"""Injection history tracking for context staleness prevention."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class InjectionHistory:
    """Tracks injection history for staleness prevention and diversity enforcement.
    
    Attributes:
        session_id: Current session identifier
        injected_symbol_ids: List of previously injected symbol IDs
        injection_counts: Map of symbol_id -> injection count
        last_injection_time: Map of symbol_id -> last injection timestamp
    """
    
    session_id: str
    injected_symbol_ids: List[str] = field(default_factory=list)
    injection_counts: Dict[str, int] = field(default_factory=dict)
    last_injection_time: Dict[str, datetime] = field(default_factory=dict)
    
    def record_injection(self, symbol_ids: List[str]) -> None:
        """Record symbols that were injected.
        
        Args:
            symbol_ids: List of symbol IDs that were injected
        """
        now = datetime.now()
        
        for sym_id in symbol_ids:
            if sym_id not in self.injected_symbol_ids:
                self.injected_symbol_ids.append(sym_id)
            
            self.injection_counts[sym_id] = self.injection_counts.get(sym_id, 0) + 1
            self.last_injection_time[sym_id] = now
    
    def should_decay(self, symbol_id: str) -> bool:
        """Check if symbol should have repetition decay applied.
        
        Args:
            symbol_id: Symbol to check
            
        Returns:
            True if symbol has been injected 3+ times
        """
        return self.injection_counts.get(symbol_id, 0) >= 3
    
    def get_injection_score_modifier(self, symbol_id: str) -> float:
        """Get combined score modifier based on history.
        
        Applies both repetition decay and temporal decay.
        
        Args:
            symbol_id: Symbol to get modifier for
            
        Returns:
            Score modifier in range [0.8, 1.0]
        """
        modifier = 1.0
        
        # Repetition decay (max 20% reduction)
        if self.should_decay(symbol_id):
            modifier *= 0.8
        
        # Temporal decay
        temporal_factor = self.temporal_decay_factor(symbol_id)
        modifier *= temporal_factor
        
        return modifier
    
    def temporal_decay_factor(self, symbol_id: str) -> float:
        """Calculate temporal decay factor.
        
        Uses exponential decay with 30-day half-life.
        
        Args:
            symbol_id: Symbol to calculate decay for
            
        Returns:
            Decay factor in range [0.01, 1.0]
        """
        if symbol_id not in self.last_injection_time:
            return 1.0
        
        last_time = self.last_injection_time[symbol_id]
        days_since = (datetime.now() - last_time).days
        
        if days_since <= 0:
            return 1.0
        
        # Exponential decay: exp(-days / 30), clamped to [0.01, 1.0]
        import math
        decay = math.exp(-days_since / 30.0)
        return max(0.01, min(1.0, decay))
    
    def enforce_diversity(
        self,
        symbols: List[Dict],
        limit: int = 3
    ) -> List[Dict]:
        """Enforce diversity constraint on symbol selection.
        
        Args:
            symbols: List of Symbol dataclasses with file_path attribute
            limit: Max symbols per file
            
        Returns:
            Filtered list respecting diversity constraint
        """
        from collections import defaultdict
        
        file_counts: Dict[str, int] = defaultdict(int)
        selected: List = []
        
        for symbol in symbols:
            file_path = getattr(symbol, 'file_path', 'unknown')
            
            if file_counts[file_path] < limit:
                selected.append(symbol)
                file_counts[file_path] += 1
        
        return selected
    
    def clear(self) -> None:
        """Clear all history (for session reset)."""
        self.injected_symbol_ids.clear()
        self.injection_counts.clear()
        self.last_injection_time.clear()