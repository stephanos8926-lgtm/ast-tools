"""Test project for AST tools E2E testing."""

import os


def create_test_project(base_dir: str) -> str:
    """Create a small Python project with known structure for testing."""
    root = os.path.join(base_dir, "test_project")
    os.makedirs(os.path.join(root, "src", "mypackage"), exist_ok=True)
    os.makedirs(os.path.join(root, "tests"), exist_ok=True)

    # Main module with classes, functions, imports
    with open(os.path.join(root, "src", "mypackage", "__init__.py"), "w") as f:
        f.write('"""My test package."""\n\n__version__ = "1.0.0"\n')

    with open(os.path.join(root, "src", "mypackage", "core.py"), "w") as f:
        f.write('''
"""Core module."""

import os
import sys
from pathlib import Path
from typing import Optional, List


class DataProcessor:
    """Processes data from various sources."""

    def __init__(self, name: str, config: Optional[dict] = None):
        self.name = name
        self.config = config or {}

    def process(self, data: List[str]) -> List[str]:
        """Process a list of strings."""
        return [self._transform(item) for item in data]

    def _transform(self, item: str) -> str:
        """Transform a single item."""
        return item.upper()

    def validate(self, data: List[str]) -> bool:
        """Validate input data."""
        return all(isinstance(d, str) for d in data)


class AdvancedProcessor(DataProcessor):
    """Advanced processor with extra features."""

    def __init__(self, name: str, config: Optional[dict] = None, verbose: bool = False):
        super().__init__(name, config)
        self.verbose = verbose

    def process(self, data: List[str]) -> List[str]:
        """Process with logging."""
        if self.verbose:
            print(f"Processing {len(data)} items")
        return super().process(data)


def create_processor(name: str, config: Optional[dict] = None) -> DataProcessor:
    """Factory function."""
    return DataProcessor(name, config)


def helper_function(x: int, y: int = 10) -> int:
    """A helper function."""
    return x + y


MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
''')

    with open(os.path.join(root, "src", "mypackage", "utils.py"), "w") as f:
        f.write('''
"""Utility functions."""

import json
import hashlib


def compute_hash(data: str) -> str:
    """Compute SHA256 hash."""
    return hashlib.sha256(data.encode()).hexdigest()


def load_json(path: str) -> dict:
    """Load JSON from file."""
    with open(path) as f:
        return json.load(f)


def save_json(path: str, data: dict) -> None:
    """Save JSON to file."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class ConfigLoader:
    """Loads configuration."""

    def __init__(self, path: str):
        self.path = path
        self._data = None

    def load(self) -> dict:
        """Load config."""
        self._data = load_json(self.path)
        return self._data
''')

    with open(os.path.join(root, "tests", "test_core.py"), "w") as f:
        f.write('''
"""Tests for core module."""

import pytest
from mypackage.core import DataProcessor, AdvancedProcessor, create_processor, helper_function


class TestDataProcessor:
    def test_create(self):
        p = DataProcessor("test")
        assert p.name == "test"

    def test_process(self):
        p = DataProcessor("test")
        result = p.process(["a", "b"])
        assert result == ["A", "B"]

    def test_validate(self):
        p = DataProcessor("test")
        assert p.validate(["a", "b"]) is True
        assert p.validate([1, 2]) is False


class TestAdvancedProcessor:
    def test_inherits(self):
        p = AdvancedProcessor("test")
        assert isinstance(p, DataProcessor)


def test_helper():
    assert helper_function(5) == 15
    assert helper_function(5, 20) == 25
''')

    return root
