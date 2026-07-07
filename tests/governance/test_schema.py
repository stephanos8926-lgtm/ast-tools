"""Tests for governance schema module."""

import tempfile
from pathlib import Path

import pytest

from ast_tools.governance.schema import (
    DEFAULT_GOVERNANCE,
    GovernanceConfig,
    init_governance_file,
    load_governance,
    validate_schema,
)

pytestmark = pytest.mark.unit


class TestGovernanceConfig:
    def test_default_layers(self):
        cfg = GovernanceConfig(DEFAULT_GOVERNANCE)
        assert len(cfg.layers) == 4
        assert "infrastructure" in cfg.layers
        assert "domain" in cfg.layers
        assert "application" in cfg.layers
        assert "presentation" in cfg.layers

    def test_default_mappings(self):
        cfg = GovernanceConfig(DEFAULT_GOVERNANCE)
        assert len(cfg.mappings) == 5
        assert cfg.mappings[0].pattern == "**/database/**"
        assert cfg.mappings[0].layer == "infrastructure"

    def test_get_layer_for_file(self):
        cfg = GovernanceConfig(DEFAULT_GOVERNANCE)
        assert cfg.get_layer_for_file("src/database/connection.py") == "infrastructure"
        assert cfg.get_layer_for_file("src/domain/models.py") == "domain"
        assert cfg.get_layer_for_file("src/api/routes.py") == "presentation"
        assert cfg.get_layer_for_file("src/some/unknown/file.py") is None

    def test_layer_rules_defaults(self):
        cfg = GovernanceConfig(DEFAULT_GOVERNANCE)
        assert cfg.layer_rules["domain"]["allowed_deps"] == ["infrastructure"]


class TestValidateSchema:
    def test_valid_default(self):
        errors = validate_schema(DEFAULT_GOVERNANCE)
        assert errors == []

    def test_missing_layers(self):
        errors = validate_schema({"version": 1})
        assert any("layers" in e for e in errors)

    def test_missing_mappings(self):
        errors = validate_schema({"version": 1, "layers": [{"name": "test"}]})
        assert any("mappings" in e for e in errors)

    def test_mapping_missing_fields(self):
        data = dict(DEFAULT_GOVERNANCE)
        data["mappings"] = [{"pattern": "**/test/**"}]  # missing layer
        errors = validate_schema(data)
        assert any("pattern" in e and "layer" in e for e in errors)


class TestLoadGovernance:
    def test_load_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "governance.yaml"
            import yaml

            path.write_text(yaml.dump(DEFAULT_GOVERNANCE))
            cfg = load_governance(path)
            assert cfg is not None
            assert "infrastructure" in cfg.layers

    def test_load_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_governance(Path(tmp) / "nonexistent.yaml")
            assert cfg is None


class TestInitGovernanceFile:
    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "governance.yaml"
            result = init_governance_file(path)
            assert result.exists()
            content = result.read_text()
            assert "infrastructure" in content
            assert "domain" in content

    def test_skips_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "governance.yaml"
            path.write_text("existing")
            result = init_governance_file(path)
            assert result.read_text() == "existing"
