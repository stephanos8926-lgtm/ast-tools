"""Tests for class hierarchy analysis tool."""

import ast
import sys
from pathlib import Path

import pytest

_src = str(Path(__file__).resolve().parent.parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from ast_tools.tools.class_hierarchy import (
    _compute_metrics,
    _compute_mro,
    _detect_interface,
    _extract_class_definitions,
    _find_methods,
    _find_subclasses,
    _get_base_names,
    _get_method_categories,
    _has_abstract_methods,
    _is_final,
    _resolve_target,
    _tool_class_hierarchy,
)

# ── helpers ────────────────────────────────────────────────────────────────


pytestmark = pytest.mark.integration

def _make_module(content: str) -> ast.Module:
    """Parse a string as Python source and return the AST module."""
    return ast.parse(content)


def _make_file(tmp_path: Path, name: str, content: str) -> Path:
    """Write *content* to ``tmp_path / name`` and return the path."""
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# =========================================================================
# TestTargetResolution
# =========================================================================


class TestTargetResolution:

    def test_class_name_only_finds_class(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "mymod.py", "class MyClass:\n    pass\n")
        # _resolve_target with workspace = str(tmp_path) — it scans files
        cls, fpath, _classes = _resolve_target("MyClass", None, str(tmp_path))
        assert cls == "MyClass"
        assert fpath is not None
        assert Path(fpath).name == "mymod.py"

    def test_file_colon_class_format(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "mod.py", "class Target:\n    pass\n")
        cls, fpath, _classes = _resolve_target("mod.py:Target", str(tmp_path / "mod.py"), str(tmp_path))
        assert cls == "Target"
        assert fpath is not None
        assert Path(fpath).name == "mod.py"

    def test_nonexistent_class_returns_none(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "mod.py", "class Real:\n    pass\n")
        cls, _fpath, _classes = _resolve_target("Fake", None, str(tmp_path))
        assert cls is None  # class not found

    def test_nonexistent_file_returns_none(self, tmp_path: Path) -> None:
        cls, fpath, _classes = _resolve_target("nope.py:MyClass", str(tmp_path / "nope.py"), str(tmp_path))
        assert cls is None
        assert fpath is None  # file doesn't exist → returns (None, None, None)

    def test_class_name_only_no_workspace_returns_none(self) -> None:
        cls, fpath, _classes = _resolve_target("MyClass", None, None)
        assert cls is None
        assert fpath is None


# =========================================================================
# TestClassExtraction
# =========================================================================


class TestClassExtraction:

    def test_parse_single_class(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "single.py", "class Hello:\n    def foo(self): pass\n")
        classes = _extract_class_definitions(str(p))
        assert "Hello" in classes
        assert isinstance(classes["Hello"], ast.ClassDef)

    def test_parse_multiple_classes(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "multi.py", "class A: pass\nclass B: pass\n")
        classes = _extract_class_definitions(str(p))
        assert "A" in classes
        assert "B" in classes

    def test_parse_nested_class(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "nested.py", "class Outer:\n    class Inner: pass\n")
        classes = _extract_class_definitions(str(p))
        # Only top-level classes are extracted
        assert "Outer" in classes
        assert "Inner" not in classes

    def test_parse_syntax_error_returns_empty(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "bad.py", "class Broken\n")
        # The function doesn't catch SyntaxError internally, but for test purposes
        # we expect it to raise. The caller handles it.
        import pytest
        with pytest.raises(SyntaxError):
            _extract_class_definitions(str(p))


# =========================================================================
# Test MRO Computation
# =========================================================================


class TestMROComputation:

    def _make_classes(self, code: str) -> dict[str, ast.ClassDef]:
        tree = ast.parse(code)
        return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}

    def test_simple_inheritance(self) -> None:
        classes = self._make_classes("""
class Base: pass
class Derived(Base): pass
""")
        mro = _compute_mro("Derived", classes)
        assert mro == ["Derived", "Base", "object"]

    def test_diamond_inheritance(self) -> None:
        classes = self._make_classes("""
class Base: pass
class Left(Base): pass
class Right(Base): pass
class Diamond(Left, Right): pass
""")
        mro = _compute_mro("Diamond", classes)
        # C3 linearization: D, L, R, B, object
        assert mro == ["Diamond", "Left", "Right", "Base", "object"]

    def test_multiple_inheritance(self) -> None:
        classes = self._make_classes("""
class A: pass
class B: pass
class C(A, B): pass
""")
        mro = _compute_mro("C", classes)
        assert mro == ["C", "A", "B", "object"]

    def test_c3_merge_conflict(self) -> None:
        classes = self._make_classes("""
class A: pass
class B: pass
class C(A, B): pass
class D(B, A): pass
class E(C, D): pass
""")
        mro = _compute_mro("E", classes)
        # This should have a merge conflict — C has [A,B] and D has [B,A]
        # The error sentinel should be in the result
        assert "<MRO_ERROR>" in mro or any("MERGE_CONFLICT" in m for m in mro), f"Expected merge conflict, got {mro}"

    def test_no_bases_returns_self_object(self) -> None:
        classes = self._make_classes("class Standalone: pass")
        mro = _compute_mro("Standalone", classes)
        assert mro == ["Standalone", "object"]

    def test_class_not_in_map(self) -> None:
        mro = _compute_mro("Ghost", {})
        assert mro == ["Ghost"]

    def test_unknown_parent_graceful(self) -> None:
        classes = self._make_classes("class Foo(Unknown): pass")
        mro = _compute_mro("Foo", classes)
        # Unknown not in map, so MRO is [Foo, Unknown] (no object added for unknown)
        assert "Foo" in mro


# =========================================================================
# Test _find_methods
# =========================================================================


class TestFindMethods:

    def test_regular_methods(self) -> None:
        tree = ast.parse("class X:\n    def a(self): pass\n    def b(self): pass\n")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _find_methods(cls) == ["a", "b"]

    def test_async_method(self) -> None:
        tree = ast.parse("class X:\n    async def go(self): pass\n")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _find_methods(cls) == ["go"]

    def test_no_methods(self) -> None:
        tree = ast.parse("class X:\n    pass\n")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _find_methods(cls) == []


# =========================================================================
# Test Method Categorization
# =========================================================================


class TestMethodCategorization:

    def test_own_methods(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "own.py", """
class Base:
    def base_method(self): pass

class Derived(Base):
    def own_method(self): pass
""")
        classes = _extract_class_definitions(str(p))
        cats = _get_method_categories("Derived", classes)
        assert "own_method" in cats["own"]
        assert "base_method" not in cats["own"]

    def test_inherited_methods(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "inherit.py", """
class Base:
    def base_method(self): pass

class Derived(Base):
    pass
""")
        classes = _extract_class_definitions(str(p))
        cats = _get_method_categories("Derived", classes)
        assert any(m["name"] == "base_method" for m in cats["inherited"])

    def test_overridden_methods(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "override.py", """
class Base:
    def common(self): pass

class Derived(Base):
    def common(self): pass
""")
        classes = _extract_class_definitions(str(p))
        cats = _get_method_categories("Derived", classes)
        assert any(o["name"] == "common" for o in cats["overrides"])

    def test_unknown_class_returns_empty(self) -> None:
        assert _get_method_categories("Ghost", {}) == {"own": [], "inherited": [], "overrides": []}


# =========================================================================
# Test Interface Detection
# =========================================================================


class TestInterfaceDetection:

    def test_abc_class(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "abc_test.py", """
from abc import ABC

class MyABC(ABC):
    pass
""")
        classes = _extract_class_definitions(str(p))
        node = classes["MyABC"]
        bases = _get_base_names(node)
        assert _detect_interface(node, bases) is True

    def test_protocol_class(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "proto_test.py", """
from typing import Protocol

class MyProto(Protocol):
    pass
""")
        classes = _extract_class_definitions(str(p))
        node = classes["MyProto"]
        bases = _get_base_names(node)
        assert _detect_interface(node, bases) is True

    def test_abstract_method(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "abstract_test.py", """
from abc import abstractmethod

class WithAbstract:
    @abstractmethod
    def doit(self): pass
""")
        classes = _extract_class_definitions(str(p))
        node = classes["WithAbstract"]
        bases = _get_base_names(node)
        # Has abstractmethod but no ABC/Protocol base
        assert _detect_interface(node, bases) is True

    def test_plain_class_not_interface(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "plain.py", """
class Plain:
    def work(self): pass
""")
        classes = _extract_class_definitions(str(p))
        node = classes["Plain"]
        bases = _get_base_names(node)
        assert _detect_interface(node, bases) is False


# =========================================================================
# Test Subclass Detection
# =========================================================================


class TestSubclassDetection:

    def test_finds_subclasses_in_same_file(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "sibling.py", """
class Parent: pass
class Child(Parent): pass
""")
        classes = _extract_class_definitions(str(tmp_path / "sibling.py"))
        subs = _find_subclasses("Parent", str(tmp_path), classes)
        assert "Child" in subs

    def test_finds_subclasses_across_files(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "parent.py", "class Parent: pass\n")
        _make_file(tmp_path, "child.py", "class Child(Parent): pass\n")
        # Need to collect classes from both files
        all_classes = {}
        for f in tmp_path.glob("*.py"):
            all_classes.update(_extract_class_definitions(str(f)))
        subs = _find_subclasses("Parent", str(tmp_path), all_classes)
        assert "Child" in subs

    def test_no_subclasses(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "only.py", "class Standalone: pass\n")
        subs = _find_subclasses("Standalone", str(tmp_path))
        assert subs == []


# =========================================================================
# Test _is_final
# =========================================================================


class TestIsFinal:

    def test_final_decorator(self) -> None:
        tree = ast.parse("@final\nclass X: pass\n")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _is_final(cls) is True

    def test_no_final(self) -> None:
        tree = ast.parse("class X: pass\n")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _is_final(cls) is False

    def test_other_decorators(self) -> None:
        tree = ast.parse("@dataclass\nclass X: pass\n")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _is_final(cls) is False
        tree2 = ast.parse("@typing.final\nclass Y: pass\n")
        cls2 = next(n for n in ast.walk(tree2) if isinstance(n, ast.ClassDef))
        assert _is_final(cls2) is True


# =========================================================================
# Test Metrics
# =========================================================================


class TestMetrics:

    def test_metrics_basic(self, tmp_path: Path) -> None:
        p = _make_file(tmp_path, "met.py", """
from abc import ABC, abstractmethod

class Base(ABC):
    @abstractmethod
    def doit(self): pass

class Concrete(Base):
    def doit(self): pass
    def extra(self): pass
""")
        classes = _extract_class_definitions(str(p))
        node = classes["Concrete"]
        bases = _get_base_names(node)
        mro = _compute_mro("Concrete", classes)
        cats = _get_method_categories("Concrete", classes)
        is_intf = _detect_interface(node, bases)
        final = _is_final(node)
        metrics = _compute_metrics("Concrete", node, classes, mro, cats, is_intf, final)

        # Concrete -> Base -> ABC -> object  (ABC is a base, not in full_classes,
        # so it gets an MRO entry of just ['ABC'])
        assert metrics["depth"] == 3
        assert metrics["num_methods"] == 2
        assert metrics["num_overrides"] == 1
        assert metrics["is_abstract"] is False
        assert metrics["is_final"] is False
        assert metrics["is_interface"] is False
        assert metrics["has_concrete_methods"] is True
        assert metrics["num_bases"] == 1


# =========================================================================
# Test _has_abstract_methods
# =========================================================================


class TestHasAbstractMethods:

    def test_abstract_method_detected(self) -> None:
        tree = ast.parse("class X:\n    @abstractmethod\n    def doit(self): pass\n")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _has_abstract_methods(cls) is True

    def test_no_abstract(self) -> None:
        tree = ast.parse("class X:\n    def doit(self): pass\n")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _has_abstract_methods(cls) is False


# =========================================================================
# Test _get_base_names
# =========================================================================


class TestGetBaseNames:

    def test_simple_name(self) -> None:
        tree = ast.parse("class Foo(Bar): pass")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _get_base_names(cls) == ["Bar"]

    def test_no_bases(self) -> None:
        tree = ast.parse("class Foo: pass")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _get_base_names(cls) == []

    def test_multiple_bases(self) -> None:
        tree = ast.parse("class Foo(A, B, C): pass")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert _get_base_names(cls) == ["A", "B", "C"]

    def test_attribute_base(self) -> None:
        tree = ast.parse("class Foo(module.Bar): pass")
        cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert "module.Bar" in _get_base_names(cls)


# =========================================================================
# Integration Tests
# =========================================================================


class TestIntegration:

    def test_tool_class_hierarchy_simple(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "s.py", """
class Animal:
    def speak(self): pass

class Dog(Animal):
    def speak(self): pass
    def wag(self): pass
""")
        # We need a workspace marker so _tool_class_hierarchy can find it
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        result = _tool_class_hierarchy({
            "target": "Dog",
            "file": str(tmp_path / "s.py"),
        })
        assert result["class"] == "Dog"
        assert "Animal" in result["bases"]
        assert "Dog" in result["mro"][0]
        assert "Animal" in result["mro"]
        assert "object" in result["mro"]
        assert result["methods"]["own"] == ["speak", "wag"]
        assert len(result["methods"]["overrides"]) == 1
        assert result["methods"]["overrides"][0]["name"] == "speak"
        assert result["metrics"]["depth"] >= 1
        assert result["metrics"]["num_methods"] == 2
        assert result["metrics"]["num_overrides"] == 1
        assert result["metrics"]["is_final"] is False
        assert result["metrics"]["is_abstract"] is False

    def test_abstract_class_detection(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "ab.py", """
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self): pass
""")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        result = _tool_class_hierarchy({
            "target": "Shape",
            "file": str(tmp_path / "ab.py"),
        })
        assert result["metrics"]["is_abstract"] is True
        assert result["metrics"]["is_interface"] is True

    def test_interface_detected(self, tmp_path: Path) -> None:
        _make_file(tmp_path, "proto.py", """
from typing import Protocol

class Drawable(Protocol):
    def draw(self): pass
""")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        result = _tool_class_hierarchy({
            "target": "Drawable",
            "file": str(tmp_path / "proto.py"),
        })
        assert result["metrics"]["is_interface"] is True
        assert "Protocol" in result["interfaces"]

    def test_class_not_found(self, tmp_path: Path) -> None:
        result = _tool_class_hierarchy({
            "target": "NonExistent",
        })
        assert "error" in result
        assert result["error_code"] == "CLASS_NOT_FOUND"

    def test_missing_target(self) -> None:
        result = _tool_class_hierarchy({})
        assert "error" in result
        assert result["error_code"] == "MISSING_PARAM"

    def test_real_ast_tools_class(self) -> None:
        """Test on GraphEngine class from ast-tools."""
        graph_engine_path = Path(__file__).resolve().parent.parent.parent / "src" / "ast_tools" / "kg" / "graph_engine.py"
        if not graph_engine_path.exists():
            pytest.skip("graph_engine.py not found")

        result = _tool_class_hierarchy({
            "target": "GraphEngine",
            "file": str(graph_engine_path),
        })
        assert result["class"] == "GraphEngine"
        assert result["bases"] == []  # No explicit bases
        assert result["mro"][0] == "GraphEngine"
        assert "object" in result["mro"]
        assert len(result["methods"]["own"]) > 0
        assert result["metrics"]["num_methods"] >= 5  # has many methods
