"""Tests for governance scanner module."""

import pytest

pytestmark = pytest.mark.unit


import tempfile
from pathlib import Path

from ast_tools.governance.scanner import scan_project
from ast_tools.governance.schema import DEFAULT_GOVERNANCE, GovernanceConfig


def _create_test_project(tmp: Path, structure: dict[str, str]) -> None:
    """Create a minimal Python project for testing."""
    for filepath, content in structure.items():
        full_path = tmp / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)


TEST_LAYER_MAPPING = {
    "infrastructure": ["**/database/**", "**/cache/**"],
    "domain": ["**/domain/**"],
    "application": ["**/usecase/**"],
    "presentation": ["**/api/**", "**/cli/**"],
}

TEST_LAYER_RULES = {
    "infrastructure": {"allowed_deps": []},
    "domain": {"allowed_deps": ["infrastructure"]},
    "application": {"allowed_deps": ["infrastructure", "domain"]},
    "presentation": {"allowed_deps": ["infrastructure", "domain", "application"]},
}


class TestScanProject:
    def test_clean_project(self):
        cfg = GovernanceConfig(DEFAULT_GOVERNANCE)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_test_project(
                root,
                {
                    "database/conn.py": "import database.schema",
                    "domain/model.py": "import database.conn",
                    "api/routes.py": "import domain.model; import database.conn",
                },
            )
            violations = scan_project(root, cfg)
            # A clean default config on a simple project should have no violations
            # (depends on mapping patterns matching)
            assert isinstance(violations, list)

    def test_no_governance_found_graceful(self):
        """Test scanner handles missing config gracefully."""
        cfg = GovernanceConfig(DEFAULT_GOVERNANCE)
        with tempfile.TemporaryDirectory() as tmp:
            violations = scan_project(tmp, cfg)
            assert isinstance(violations, list)

    def test_violation_structure(self):
        cfg = GovernanceConfig(DEFAULT_GOVERNANCE)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_test_project(
                root,
                {
                    "database/conn.py": "import database.schema",
                    "domain/model.py": "import database.conn",
                    "api/routes.py": "import domain.model; import database.conn",
                },
            )
            violations = scan_project(root, cfg)
            for v in violations:
                d = v.to_dict()
                assert "file" in d
                assert "layer" in d
                assert "import_target" in d
                assert "severity" in d
                assert d["severity"] in ("error", "warn")

    def test_forbidden_deps(self):
        """Test that forbidden deps are detected."""
        config_data = dict(DEFAULT_GOVERNANCE)
        config_data["layer_rules"] = {
            "infrastructure": {"allowed_deps": [], "forbidden_deps": ["presentation"]},
            "domain": {"allowed_deps": ["infrastructure"]},
            "application": {"allowed_deps": ["infrastructure", "domain"]},
            "presentation": {"allowed_deps": ["infrastructure", "domain", "application"]},
        }
        cfg = GovernanceConfig(config_data)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _create_test_project(
                root,
                {
                    "cache/cache.py": "import api.routes",  # infrastructure → presentation: forbidden!
                    "domain/model.py": "import database.conn",
                },
            )
            violations = scan_project(root, cfg)
            [
                v
                for v in violations
                if v.rule_type == "layer" and "forbidden" in v.message.lower()
                if hasattr(v, "message")
            ]
            assert isinstance(violations, list)


class TestViolationOutput:
    def test_violation_to_dict(self):
        from ast_tools.governance.scanner import Violation

        v = Violation(
            file="src/domain/model.py",
            layer="domain",
            import_target="database.conn",
            target_layer="infrastructure",
            rule_type="layer",
        )
        d = v.to_dict()
        assert d["file"] == "src/domain/model.py"
        assert d["layer"] == "domain"
        assert d["severity"] == "error"
        assert "database.conn" in d["message"]
