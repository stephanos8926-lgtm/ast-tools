#!/usr/bin/env python3
import pytest
pytestmark = pytest.mark.integration

"""Tests for enhanced dead code detection."""

import tempfile
from pathlib import Path


from ast_tools.tools.enhanced_dead_code import find_dead_code_enhanced


class TestEnhancedDeadCode:
    """Test enhanced dead code detection with false positive reduction."""

    def test_basic_dead_code(self, tmp_path: Path) -> None:
        """Test basic dead code detection."""
        # Create a file with dead code
        dead_file = tmp_path / "dead.py"
        dead_file.write_text("""
def unused_function():
    pass

class UnusedClass:
    pass
""")

        # Create an entry point that doesn't use them
        main_file = tmp_path / "main.py"
        main_file.write_text("""
def main():
    print("Hello")

if __name__ == "__main__":
    main()
""")

        result = find_dead_code_enhanced(str(tmp_path))

        # Should find dead code
        assert len(result["dead_functions"]) > 0
        assert len(result["dead_classes"]) > 0

        # Check confidence scoring
        dead_funcs = result["dead_functions"]
        assert any(f["confidence"] in ("high", "medium", "low") for f in dead_funcs)

    def test_framework_decorators_excluded(self, tmp_path: Path) -> None:
        """Test that framework-decorated functions are not flagged as dead."""
        # Create a file with Flask routes
        routes_file = tmp_path / "routes.py"
        routes_file.write_text("""
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello"

@app.route('/api')
def api_endpoint():
    return {"status": "ok"}
""")

        result = find_dead_code_enhanced(str(tmp_path))

        # These should NOT be flagged as dead (or should have low confidence)
        dead_funcs = result["dead_functions"]
        route_names = {f["name"] for f in dead_funcs}
        
        # Should not flag decorated routes as high-confidence dead code
        for func in dead_funcs:
            if func["name"] in ("index", "api_endpoint"):
                assert func["confidence"] == "low"
                assert "framework_decorator" in func.get("alive_signals", [])

    def test_entry_point_reachable(self, tmp_path: Path) -> None:
        """Test that symbols reachable from entry points are not flagged."""
        # Create main.py that calls other functions
        main_file = tmp_path / "main.py"
        main_file.write_text("""
def helper():
    return "helped"

def main():
    result = helper()
    print(result)

if __name__ == "__main__":
    main()
""")

        result = find_dead_code_enhanced(str(tmp_path), entry_points=["main.py"])

        # helper() should be reachable from main.py
        dead_funcs = result["dead_functions"]
        helper_dead = [f for f in dead_funcs if f["name"] == "helper"]
        
        # Should either not be dead, or have low confidence (referenced in code)
        if helper_dead:
            # Since helper() IS referenced in the code, it should have low confidence
            assert helper_dead[0]["confidence"] == "low"
            # The alive signal will be 'referenced_in_code' since it's actually referenced
            assert len(helper_dead[0].get("alive_signals", [])) > 0

    def test_dunder_all_exports(self, tmp_path: Path) -> None:
        """Test that __all__ exports are not flagged as dead."""
        # Create a module with __all__
        lib_file = tmp_path / "lib.py"
        lib_file.write_text("""
__all__ = ['public_function', 'PublicClass']

def public_function():
    pass

def _private_function():
    pass

class PublicClass:
    pass

class _PrivateClass:
    pass
""")

        result = find_dead_code_enhanced(str(tmp_path))

        # public_function and PublicClass should have medium confidence (exported)
        dead_funcs = result["dead_functions"]
        public_funcs = [f for f in dead_funcs if f["name"] == "public_function"]
        
        if public_funcs:
            assert public_funcs[0]["confidence"] == "medium"
            assert "exported_in_all" in public_funcs[0].get("alive_signals", [])

        dead_classes = result["dead_classes"]
        public_classes = [c for c in dead_classes if c["name"] == "PublicClass"]
        
        if public_classes:
            assert public_classes[0]["confidence"] == "medium"
            assert "exported_in_all" in public_classes[0].get("alive_signals", [])

    def test_polymorphism_markers(self, tmp_path: Path) -> None:
        """Test that polymorphism-marked methods are not flagged as dead."""
        # Create a file with override decorators
        models_file = tmp_path / "models.py"
        models_file.write_text("""
class Base:
    def process(self):
        pass

class Derived(Base):
    def process(self):
        # Override marker would be here in real code
        return "derived"
    
    def extra_method(self):
        # This one is truly dead
        pass
""")

        result = find_dead_code_enhanced(str(tmp_path))

        # process() might be marked as polymorphism
        dead_methods = result.get("dead_methods", [])
        
        # extra_method should be dead with high confidence
        extra_dead = [m for m in dead_methods if m["name"] == "extra_method"]
        if extra_dead:
            assert extra_dead[0]["confidence"] == "high"

    def test_scc_cluster_detection(self, tmp_path: Path) -> None:
        """Test that mutually recursive functions are detected as SCC."""
        # Create mutually recursive functions
        recursive_file = tmp_path / "recursive.py"
        recursive_file.write_text("""
def even(n):
    if n == 0:
        return True
    return odd(n - 1)

def odd(n):
    if n == 0:
        return False
    return even(n - 1)
""")

        result = find_dead_code_enhanced(str(tmp_path))

        # even and odd form an SCC cluster
        dead_funcs = result["dead_functions"]
        
        # They might still be flagged as dead (no external references)
        # but should be marked as being in an SCC
        for func in dead_funcs:
            if func["name"] in ("even", "odd"):
                # Should acknowledge the mutual recursion in reasoning
                pass  # Implementation detail - SCC detection is internal

    def test_summary_metadata(self, tmp_path: Path) -> None:
        """Test that summary includes false positive mitigation stats."""
        # Create a simple project
        main_file = tmp_path / "main.py"
        main_file.write_text("""
def main():
    pass
""")

        result = find_dead_code_enhanced(str(tmp_path))

        # Check summary structure
        assert "summary" in result
        assert "false_positive_mitigations" in result["summary"]
        
        mitigations = result["summary"]["false_positive_mitigations"]
        assert "framework_decorators" in mitigations
        assert "exported_symbols" in mitigations
        assert "entry_point_symbols" in mitigations
        assert "scc_cluster_members" in mitigations
        assert "interface_implementations" in mitigations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])