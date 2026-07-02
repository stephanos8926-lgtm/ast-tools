"""Tests for the file_related_suggest tool, including call graph integration."""

import pytest
from pathlib import Path
from unittest.mock import patch

from ast_tools.tools.file_related import _tool_file_related_suggest


# --- Test Data Setup ---

@pytest.fixture(scope="module")
def workspace(tmp_path_factory) -> Path:
    """Create a temporary workspace with test project structure."""
    workspace_path = tmp_path_factory.mktemp("workspace")

    # Create a function file
    (workspace_path / "src" / "my_module").mkdir(parents=True, exist_ok=True)
    (workspace_path / "src" / "my_module" / "target_file.py").write_text(
        """
def function_to_call():
    pass

class MyClass:
    def method_to_call(self):
        pass
"""
    )

    # Create a file that calls the function
    (workspace_path / "src" / "another_module").mkdir(parents=True, exist_ok=True)
    (workspace_path / "src" / "another_module" / "caller_file.py").write_text(
        """
from src.my_module.target_file import function_to_call, MyClass

def some_other_function():
    function_to_call()
    instance = MyClass()
    instance.method_to_call()
    print("Called target functions")
"""
    )

    # Create a file that calls a method indirectly
    (workspace_path / "src" / "indirect_caller").mkdir(parents=True, exist_ok=True)
    (workspace_path / "src" / "indirect_caller" / "indirect_caller_file.py").write_text(
        """
from src.my_module.target_file import MyClass

class Wrapper:
    def call_method(self):
        instance = MyClass()
        instance.method_to_call()

def wrapper_caller():
    w = Wrapper()
    w.call_method()
"""
    )

    # Create a file that imports the module but doesn't call directly
    (workspace_path / "src" / "importer_module").mkdir(parents=True, exist_ok=True)
    (workspace_path / "src" / "importer_module" / "importer_file.py").write_text(
        """
import src.my_module.target_file
print("Imported target module")
"""
    )

    return workspace_path


# --- Mock-based tests ---

@patch("ast_tools.tools.file_related._ast_find_callers")
def test_call_graph_strategy_direct_call(mock_find_callers, workspace):
    """Verify that a file which calls a function from the target appears as
    a 'call_graph' suggestion."""
    mock_find_callers.side_effect = lambda sym, root, max_files=100, max_depth=50: (
        [{"file": "src/another_module/caller_file.py", "line": 5,
          "caller": "some_other_function", "context": "function_to_call()"}]
        if sym == "function_to_call"
        else [{"file": "src/another_module/caller_file.py", "line": 7,
               "caller": "some_other_function", "context": "instance.method_to_call()"}]
        if sym == "MyClass.method_to_call"
        else []
    )

    target = workspace / "src" / "my_module" / "target_file.py"
    result = _tool_file_related_suggest({
        "file_path": str(target),
        "workspace": str(workspace),
        "max_suggestions": 10,
        "include_imports": False,
        "include_tests": False,
    })

    call_graph_suggestions = [s for s in result["suggestions"] if s["reason"] == "call_graph"]
    assert len(call_graph_suggestions) == 1, f"Expected 1 call_graph suggestion, got {len(call_graph_suggestions)}"

    sugg = call_graph_suggestions[0]
    caller_path = str(workspace / "src" / "another_module" / "caller_file.py")
    assert sugg["path"] == caller_path
    assert 0.55 <= sugg["confidence"] <= 0.60
    assert "function_to_call" in sugg["explanation"] or "MyClass.method_to_call" in sugg["explanation"]


@patch("ast_tools.tools.file_related._ast_find_callers")
def test_call_graph_strategy_no_callers(mock_find_callers, workspace):
    """Verify that a file with no callers yields zero 'call_graph' suggestions."""
    mock_find_callers.return_value = []

    target = workspace / "src" / "my_module" / "target_file.py"
    result = _tool_file_related_suggest({
        "file_path": str(target),
        "workspace": str(workspace),
        "max_suggestions": 10,
        "include_imports": False,
        "include_tests": False,
    })

    call_graph_suggestions = [s for s in result["suggestions"] if s["reason"] == "call_graph"]
    assert len(call_graph_suggestions) == 0


@patch("ast_tools.tools.file_related._ast_find_callers")
def test_call_graph_multiple_files(mock_find_callers, workspace):
    """Verify that callers from multiple files are all suggested."""
    mock_find_callers.side_effect = lambda sym, root, max_files=100, max_depth=50: (
        [{"file": "src/another_module/caller_file.py", "line": 5,
          "caller": "some_other_function", "context": "function_to_call()"}]
        if sym == "function_to_call"
        else [
            {"file": "src/another_module/caller_file.py", "line": 7,
             "caller": "some_other_function", "context": "instance.method_to_call()"},
            {"file": "src/indirect_caller/indirect_caller_file.py", "line": 8,
             "caller": "Wrapper.call_method", "context": "instance.method_to_call()"},
        ]
        if sym == "MyClass.method_to_call"
        else []
    )

    target = workspace / "src" / "my_module" / "target_file.py"
    result = _tool_file_related_suggest({
        "file_path": str(target),
        "workspace": str(workspace),
        "max_suggestions": 10,
        "include_imports": False,
        "include_tests": False,
    })

    call_graph_suggestions = [s for s in result["suggestions"] if s["reason"] == "call_graph"]
    assert len(call_graph_suggestions) >= 2

    paths = [s["path"] for s in call_graph_suggestions]
    assert str(workspace / "src" / "another_module" / "caller_file.py") in paths
    assert str(workspace / "src" / "indirect_caller" / "indirect_caller_file.py") in paths


@patch("ast_tools.tools.file_related._ast_find_callers")
def test_call_graph_excludes_importer_file(mock_find_callers, workspace):
    """Verify that a file which only imports the target (no function calls)
    is NOT suggested by 'call_graph' — the mock returns nothing for 'import'."""
    mock_find_callers.return_value = []

    target = workspace / "src" / "my_module" / "target_file.py"
    result = _tool_file_related_suggest({
        "file_path": str(target),
        "workspace": str(workspace),
        "max_suggestions": 10,
        "include_imports": False,
        "include_tests": False,
    })

    call_graph_suggestions = [s for s in result["suggestions"] if s["reason"] == "call_graph"]
    importer_path = str(workspace / "src" / "importer_module" / "importer_file.py")
    for s in call_graph_suggestions:
        assert s["path"] != importer_path, (
            f"Importer file '{importer_path}' should not appear in call_graph suggestions"
        )


@patch("ast_tools.tools.file_related._ast_find_callers")
def test_call_graph_dedup_with_imports(mock_find_callers, workspace):
    """Verify that when both 'imported_by' and 'call_graph' find the same file,
    only the higher-confidence entry survives dedup."""
    mock_find_callers.side_effect = lambda sym, root, max_files=100, max_depth=50: (
        [{"file": "src/another_module/caller_file.py", "line": 5,
          "caller": "some_other_function", "context": "function_to_call()"}]
        if sym in ("function_to_call", "MyClass.method_to_call")
        else []
    )

    target = workspace / "src" / "my_module" / "target_file.py"
    result = _tool_file_related_suggest({
        "file_path": str(target),
        "workspace": str(workspace),
        "max_suggestions": 10,
        "include_imports": True,
        "include_tests": False,
    })

    # At most one entry per path
    paths = [s["path"] for s in result["suggestions"]]
    assert len(paths) == len(set(paths)), "Duplicate paths found after dedup"
