"""Tests for InjectionHistory - session tracking, staleness, diversity."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from ast_tools.context.history import InjectionHistory


class TestInjectionHistory:
    """Test session-based injection history tracking."""
    
    def test_history_init(self):
        """Test history initialization."""
        history = InjectionHistory(session_id="test-session")
        assert history.session_id == "test-session"
        assert history.injected_symbol_ids == []
        assert history.injection_counts == {}
        assert history.last_injection_time == {}
    
    def test_record_injection(self):
        """Test recording injected symbols."""
        history = InjectionHistory(session_id="test-session")
        
        history.record_injection(["sym-1", "sym-2", "sym-3"])
        
        assert history.injected_symbol_ids == ["sym-1", "sym-2", "sym-3"]
        assert history.injection_counts["sym-1"] == 1
        assert history.injection_counts["sym-2"] == 1
        assert history.injection_counts["sym-3"] == 1
        assert "sym-1" in history.last_injection_time
    
    def test_repetition_decay(self):
        """Test decay after repeated injections."""
        history = InjectionHistory(session_id="test-session")
        
        # Inject same symbols 3 times
        for _ in range(3):
            history.record_injection(["sym-1", "sym-2"])
        
        # Should trigger repetition decay flag
        assert history.should_decay("sym-1") is True
        assert history.should_decay("sym-2") is True
    
    def test_diversity_enforcement(self):
        """Test max symbols per file enforcement."""
        history = InjectionHistory(session_id="test-session")
        
        # Mock symbols with file info
        symbols = [
            {"id": f"sym-{i}", "file_path": "same.py"} for i in range(10)
        ]
        
        filtered = history.enforce_diversity(symbols, limit=3)
        
        assert len(filtered) == 3
        assert all(s["file_path"] == "same.py" for s in filtered)
    
    def test_temporal_decay(self):
        """Test temporal decay calculation."""
        history = InjectionHistory(session_id="test-session")
        
        # Fresh injection (should not decay)
        history.record_injection(["sym-fresh"])
        assert history.temporal_decay_factor("sym-fresh") == 1.0
        
        # Old injection (should decay)
        history.last_injection_time["sym-old"] = datetime.now() - timedelta(days=10)
        assert history.temporal_decay_factor("sym-old") < 1.0
    
    def test_get_injection_score_modifier(self):
        """Get combined modifier for a symbol."""
        history = InjectionHistory(session_id="test-session")
        history.record_injection(["sym-repeated"])
        
        # Inject 3 more times
        for _ in range(3):
            history.record_injection(["sym-repeated"])
        
        modifier = history.get_injection_score_modifier("sym-repeated")
        # Should be reduced by repetition decay
        assert modifier < 1.0
        assert modifier >= 0.8  # 20% max reduction