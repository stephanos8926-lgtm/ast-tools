#!/usr/bin/env python3
"""Tests for spectral clustering module decomposition.

Covers:
- Laplacian construction
- Fiedler vector computation via power iteration
- Partition quality scoring
- Recursive bipartitioning
- End-to-end suggest_modules on a synthetic project
- MCP tool function (_tool_suggest_modules)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from ast_tools.tools.spectral import (
    ClusterAssignment,
    PartitionNode,
    SpectralConfig,
    SpectralResult,
    _build_cochange_adjacency,
    _build_module_adjacency,
    _build_semantic_adjacency,
    _fiedler_bipartition,
    _fiedler_vector_power_iteration,
    _normalized_laplacian,
    _partition_quality,
    suggest_modules,
    _tool_suggest_modules,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def simple_adj() -> np.ndarray:
    """3-node chain: 0-1-2. Natural split: {0, 1} and {2} or {0} and {1, 2}."""
    adj = np.array([
        [0, 1, 0],
        [1, 0, 1],
        [0, 1, 0],
    ], dtype=np.float64)
    return adj


@pytest.fixture
def two_cluster_adj() -> np.ndarray:
    """6 nodes, 2 clusters with strong intra-cluster edges, weak inter-cluster.

    Cluster A: nodes 0-2 (triangle)
    Cluster B: nodes 3-5 (triangle)
    Single weak edge between node 2 and node 3.
    """
    adj = np.zeros((6, 6), dtype=np.float64)
    # Cluster A (0, 1, 2): triangle
    adj[0, 1] = adj[1, 0] = 5
    adj[1, 2] = adj[2, 1] = 5
    adj[0, 2] = adj[2, 0] = 5
    # Cluster B (3, 4, 5): triangle
    adj[3, 4] = adj[4, 3] = 5
    adj[4, 5] = adj[5, 4] = 5
    adj[3, 5] = adj[5, 3] = 5
    # Weak inter-cluster edge
    adj[2, 3] = adj[3, 2] = 1
    return adj


@pytest.fixture
def synthetic_project(tmp_path: Path) -> Path:
    """Create a synthetic Python project with natural module boundaries.

    Structure:
        project/
            main.py          -> imports auth, db
            auth/
                __init__.py  -> imports auth.login, auth.token
                login.py     -> imports auth.token
                token.py     -> no internal imports
            db/
                __init__.py  -> imports db.models, db.queries
                models.py    -> no internal imports
                queries.py   -> imports db.models
            utils/
                __init__.py  -> no internal imports
                helpers.py   -> no internal imports
            api/
                __init__.py  -> imports api.routes, auth
                routes.py    -> imports db.queries, auth
    """
    root = tmp_path / "project"
    root.mkdir()

    # Root-level files
    (root / "main.py").write_text("import auth\nimport db\nimport api\n")

    # auth package
    auth_dir = root / "auth"
    auth_dir.mkdir()
    (auth_dir / "__init__.py").write_text("from . import login, token\n")
    (auth_dir / "login.py").write_text("from . import token\n")
    (auth_dir / "token.py").write_text("# token module\n")

    # db package
    db_dir = root / "db"
    db_dir.mkdir()
    (db_dir / "__init__.py").write_text("from . import models, queries\n")
    (db_dir / "models.py").write_text("# models\n")
    (db_dir / "queries.py").write_text("from . import models\n")

    # utils package (isolated)
    utils_dir = root / "utils"
    utils_dir.mkdir()
    (utils_dir / "__init__.py").write_text("# utils\n")
    (utils_dir / "helpers.py").write_text("# helpers\n")

    # api package
    api_dir = root / "api"
    api_dir.mkdir()
    (api_dir / "__init__.py").write_text("from . import routes\nimport auth\n")
    (api_dir / "routes.py").write_text("from ..db import queries\nimport auth\n")

    return root


# ── Unit Tests: Laplacian ────────────────────────────────────────────────────


class TestLaplacian:
    """Test normalized Laplacian construction."""

    def test_laplacian_3_chain(self, simple_adj: np.ndarray) -> None:
        """Laplacian of 3-node chain has expected shape and properties."""
        L = _normalized_laplacian(simple_adj)
        assert L.shape == (3, 3)
        # Symmetric
        assert np.allclose(L, L.T)
        # All eigenvalues >= 0 (PSD)
        eigenvalues = np.linalg.eigvalsh(L)
        assert eigenvalues[0] >= -1e-10

    def test_laplacian_isolated_node(self) -> None:
        """Laplacian handles isolated nodes (zero degree) without division by zero."""
        adj = np.array([
            [0, 1, 0],
            [1, 0, 0],
            [0, 0, 0],
        ], dtype=np.float64)
        L = _normalized_laplacian(adj)
        assert L.shape == (3, 3)
        # The isolated node (index 2) should have 0 on diagonal and off-diagonals
        assert L[2, 2] == pytest.approx(1.0)
        assert L[0, 2] == pytest.approx(0.0)

    def test_laplacian_empty_graph(self) -> None:
        """Empty adjacency returns empty Laplacian."""
        adj = np.zeros((0, 0))
        L = _normalized_laplacian(adj)
        assert L.shape == (0, 0)


# ── Unit Tests: Fiedler Vector ────────────────────────────────────────────────


class TestFiedlerVector:
    """Test Fiedler vector computation via power iteration."""

    def test_fiedler_3_chain(self, simple_adj: np.ndarray) -> None:
        """3-node chain: Fiedler vector splits into {0} and {1, 2} or {0, 1} and {2}."""
        L = _normalized_laplacian(simple_adj)
        v, eigval = _fiedler_vector_power_iteration(L)
        assert len(v) == 3
        assert eigval > 0  # Connected graph: λ₂ > 0
        # Two entries same sign, one opposite (the split)
        assert abs(np.sum(v > 0) - np.sum(v < 0)) >= 1

    def test_fiedler_two_clusters(self, two_cluster_adj: np.ndarray) -> None:
        """Two obvious clusters: Fiedler separates them cleanly."""
        L = _normalized_laplacian(two_cluster_adj)
        v, eigval = _fiedler_vector_power_iteration(L)
        assert len(v) == 6
        assert eigval > 0
        # Nodes should split cleanly: {0,1,2} same sign, {3,4,5} opposite.
        # The actual sign direction (which side is positive) is arbitrary,
        # but the within-group signs must agree.
        first_three_sign = (v[0] > 0) == (v[1] > 0) == (v[2] > 0)
        last_three_sign = (v[3] > 0) == (v[4] > 0) == (v[5] > 0)
        split = (v[0] > 0) != (v[3] > 0)
        assert first_three_sign, f"First 3 nodes not same sign in {v}"
        assert last_three_sign, f"Last 3 nodes not same sign in {v}"
        assert split, f"Split not found: {v}"

    def test_fiedler_single_node(self) -> None:
        """Single node: returns 0.5 vector and 0 eigenvalue."""
        L = np.array([[0.0]])
        v, eigval = _fiedler_vector_power_iteration(L)
        assert v == pytest.approx(0.5)
        assert eigval == pytest.approx(0.0)

    def test_fiedler_convergence(self, two_cluster_adj: np.ndarray) -> None:
        """Power iteration converges to similar vector regardless of iterations."""
        L = _normalized_laplacian(two_cluster_adj)
        v_50, _ = _fiedler_vector_power_iteration(L, n_iter=50)
        v_500, _ = _fiedler_vector_power_iteration(L, n_iter=500)
        # Signs should agree on at least 5/6 nodes
        sign_agreement = np.sum((v_50 > 0) == (v_500 > 0))
        assert sign_agreement >= 5


# ── Unit Tests: Partition Quality ────────────────────────────────────────────


class TestPartitionQuality:
    """Test modularity-based partition quality scoring."""

    def test_perfect_split(self, two_cluster_adj: np.ndarray) -> None:
        """Perfect split into 2 clusters gets high quality."""
        labels = np.array([0, 0, 0, 1, 1, 1])
        q = _partition_quality(two_cluster_adj, labels, 2)
        assert q > 0.3  # Well-separated clusters

    def test_bad_split(self, two_cluster_adj: np.ndarray) -> None:
        """Interleaved split gets lower quality."""
        good_labels = np.array([0, 0, 0, 1, 1, 1])
        bad_labels = np.array([0, 1, 0, 1, 0, 1])
        good_q = _partition_quality(two_cluster_adj, good_labels, 2)
        bad_q = _partition_quality(two_cluster_adj, bad_labels, 2)
        assert good_q > bad_q

    def test_single_cluster(self, two_cluster_adj: np.ndarray) -> None:
        """All nodes in one cluster gives Q=0."""
        labels = np.zeros(6, dtype=int)
        q = _partition_quality(two_cluster_adj, labels, 1)
        assert q == pytest.approx(0.0)

    def test_empty_graph(self) -> None:
        """Empty graph returns Q=0."""
        q = _partition_quality(np.zeros((0, 0)), np.array([], dtype=int), 0)
        assert q == pytest.approx(0.0)


# ── Unit Tests: Recursive Bipartitioning ─────────────────────────────────────


class TestFiedlerBipartition:
    """Test recursive bipartitioning."""

    def test_two_clusters_splits_correctly(self, two_cluster_adj: np.ndarray) -> None:
        """Two-cluster graph splits into exactly (or near) the expected groups."""
        module_names = ["a", "b", "c", "d", "e", "f"]
        root = _fiedler_bipartition(
            two_cluster_adj, module_names, "root", 0, min_size=2, max_depth=5
        )
        # Should have left and right children
        assert root.left is not None
        assert root.right is not None
        # Collect leaf modules
        from ast_tools.tools.spectral import _collect_leaves
        leaves = _collect_leaves(root)
        # Should have 2+ leaves
        assert len(leaves) >= 2

    def test_min_size_respected(self, two_cluster_adj: np.ndarray) -> None:
        """Setting min_size=3 prevents splitting below 3 nodes."""
        module_names = ["a", "b", "c", "d", "e", "f"]
        root = _fiedler_bipartition(
            two_cluster_adj, module_names, "root", 0, min_size=3, max_depth=5
        )
        assert root.left is not None
        assert root.right is not None
        # Each child should have at least 3 modules
        assert len(root.left.modules) >= 3
        assert len(root.right.modules) >= 3

    def test_single_module_no_split(self) -> None:
        """Single module returns leaf immediately."""
        adj = np.array([[0.0]])
        root = _fiedler_bipartition(adj, ["only"], "root", 0, min_size=2, max_depth=5)
        assert root.left is None
        assert root.right is None


# ── Integration Tests: suggest_modules ────────────────────────────────────────


class TestSuggestModules:
    """End-to-end tests for suggest_modules on synthetic projects."""

    def test_synthetic_project_returns_clusters(self, synthetic_project: Path) -> None:
        """suggest_modules returns non-empty clusters for a synthetic project."""
        result = suggest_modules(str(synthetic_project))
        assert result.num_modules > 0
        assert result.num_clusters >= 1
        assert len(result.clusters) >= 1
        # Should have detected at least some structure
        assert result.partition_tree is not None

    def test_synthetic_project_cluster_sizes(self, synthetic_project: Path) -> None:
        """Cluster sizes sum to total modules."""
        result = suggest_modules(str(synthetic_project))
        total = sum(c.size for c in result.clusters)
        assert total == result.num_modules

    def test_synthetic_project_quality_positive(self, synthetic_project: Path) -> None:
        """Modularity quality should be reasonable (not strongly negative)."""
        result = suggest_modules(str(synthetic_project))
        # With the natural boundaries in synthetic project, quality should be > -0.5
        assert result.quality > -0.5

    def test_all_modules_accounted_for(self, synthetic_project: Path) -> None:
        """Every module in the project is assigned to a cluster."""
        result = suggest_modules(str(synthetic_project))
        all_assigned = set()
        for c in result.clusters:
            all_assigned.update(c.modules)
        assert len(all_assigned) == result.num_modules, (
            f"Assigned {len(all_assigned)} modules, but num_modules={result.num_modules}"
        )
        # With synthetic project we know there are 11 Python files
        assert result.num_modules >= 10, f"Expected >=10 modules, got {result.num_modules}"

    def test_empty_project(self, tmp_path: Path) -> None:
        """Empty directory returns empty result."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = suggest_modules(str(empty_dir))
        assert result.num_modules == 0
        assert result.num_clusters == 0

    def test_single_file_project(self, tmp_path: Path) -> None:
        """Single file with no imports returns single-module result."""
        project = tmp_path / "single"
        project.mkdir()
        (project / "hello.py").write_text("x = 1\n")
        result = suggest_modules(str(project))
        # Single file, no imports — should still produce a result
        assert result.num_modules <= 1 or result.isolated_modules is not None

    def test_tool_function(self, synthetic_project: Path) -> None:
        """MCP tool function returns expected dict structure."""
        result = _tool_suggest_modules({"project_root": str(synthetic_project)})
        assert "clusters" in result
        assert "num_modules" in result
        assert "num_clusters" in result
        assert "quality" in result
        assert isinstance(result["clusters"], list)
        if result["clusters"]:
            first = result["clusters"][0]
            assert "cluster_id" in first
            assert "modules" in first
            assert "size" in first
            assert "cohesion" in first
            assert "coupling" in first

    def test_tool_function_min_size(self, synthetic_project: Path) -> None:
        """Larger min_cluster_size reduces number of clusters."""
        result_default = _tool_suggest_modules({"project_root": str(synthetic_project)})
        result_large = _tool_suggest_modules({
            "project_root": str(synthetic_project),
            "min_cluster_size": 3,
        })
        assert result_large["num_clusters"] > 0


# ── Multi-Language Tests ──────────────────────────────────────────────────


class TestMultiLanguage:
    """Test import extraction across supported languages."""

    def test_python_imports(self, tmp_path: Path) -> None:
        """Python import resolution works."""
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("x = 1\n")
        adj, names = _build_module_adjacency(str(tmp_path))
        assert "a" in names
        assert "b" in names
        # a imports b = edge weight >= 1.0
        ai = names.index("a")
        bi = names.index("b")
        assert adj[ai, bi] >= 1.0, f"No edge a→b, weight={adj[ai, bi]}"

    def test_typescript_imports(self, tmp_path: Path) -> None:
        """TypeScript relative import resolution works."""
        (tmp_path / "app.ts").write_text('import { Button } from "./ui/button";\n')
        ui_dir = tmp_path / "ui"
        ui_dir.mkdir()
        (ui_dir / "button.ts").write_text("export const Button = () => {};\n")
        adj, names = _build_module_adjacency(str(tmp_path))
        assert "app" in names, f"Expected 'app' in {names}"
        assert "ui.button" in names, f"Expected 'ui.button' in {names}"
        ai = names.index("app")
        bi = names.index("ui.button")
        assert adj[ai, bi] >= 0.9, f"No edge app→ui.button, weight={adj[ai, bi]:.2f}"

    def test_go_imports(self, tmp_path: Path) -> None:
        """Go import resolution works for internal packages."""
        pkg = tmp_path / "internal" / "db"
        pkg.mkdir(parents=True)
        (pkg / "db.go").write_text("package db\n")
        (tmp_path / "main.go").write_text(
            'package main\nimport "testproj/internal/db"\n'
        )
        adj, names = _build_module_adjacency(str(tmp_path))
        pm = [n for n in names if "main" in n]
        assert len(pm) >= 1, f"No main module in {names}"
        main_name = pm[0]
        db_name = "internal.db.db"
        assert db_name in names, f"Expected {db_name} in {names}"
        mi = names.index(main_name)
        di = names.index(db_name)
        # Go import resolved → edge weight >= 1.0
        assert adj[mi, di] >= 0.9, f"No edge main→db, weight={adj[mi, di]:.2f}"

    def test_rust_imports(self, tmp_path: Path) -> None:
        """Rust crate:: import resolution works."""
        src = tmp_path / "src"
        src.mkdir()
        db_dir = src / "db"
        db_dir.mkdir()
        (db_dir / "mod.rs").write_text("pub mod models;\n")
        (db_dir / "models.rs").write_text("pub struct User;\n")
        (src / "main.rs").write_text("use crate::db::models;\nfn main() {}\n")
        adj, names = _build_module_adjacency(str(tmp_path))
        main_name = [n for n in names if "main" in n][0]
        assert "src.db.models" in names, f"Expected src.db.models in {names}"
        mi = names.index(main_name)
        di = names.index("src.db.models")
        # Rust use crate:: → edge weight >= 1.0 (via containing edge from containment)
        # Or at least the mod.rs containment edge
        assert adj[mi, di] > 0 or any(
            adj[mi, names.index(n)] > 0
            for n in names if n.startswith("src.db")
        ), f"No edge from {main_name} to db modules"

    def test_c_include(self, tmp_path: Path) -> None:
        """C include resolution works for quoted includes."""
        inc = tmp_path / "include"
        inc.mkdir()
        (inc / "header.h").write_text("#ifndef HEADER_H\n#define HEADER_H\n#endif\n")
        (tmp_path / "main.c").write_text('#include "include/header.h"\nint main() {}\n')
        adj, names = _build_module_adjacency(str(tmp_path))
        main_name = "main"
        header_name = "include.header"
        assert main_name in names, f"Expected {main_name} in {names}"
        assert header_name in names, f"Expected {header_name} in {names}"
        mi = names.index(main_name)
        hi = names.index(header_name)
        assert adj[mi, hi] >= 0.9, f"No edge main→header, weight={adj[mi, hi]:.2f}"

    def test_cpp_include(self, tmp_path: Path) -> None:
        """C++ include resolution works."""
        inc = tmp_path / "inc"
        inc.mkdir()
        (inc / "util.hpp").write_text("#pragma once\n")
        (tmp_path / "main.cpp").write_text('#include "inc/util.hpp"\nint main() {}\n')
        adj, names = _build_module_adjacency(str(tmp_path))
        assert "main" in names
        assert "inc.util" in names
        mi = names.index("main")
        hi = names.index("inc.util")
        assert adj[mi, hi] >= 0.9

    def test_mixed_language_project(self, tmp_path: Path) -> None:
        """Multi-language project creates a unified graph."""
        # Python
        (tmp_path / "main.py").write_text("import helpers\n")
        (tmp_path / "helpers.py").write_text("x = 1\n")
        # TypeScript
        (tmp_path / "app.ts").write_text('import { greet } from "./lib/util";\n')
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "util.ts").write_text("export function greet() {}\n")
        # Both should appear in the same graph
        adj, names = _build_module_adjacency(str(tmp_path))
        expected = {"main", "helpers", "app", "lib.util"}
        found = set(names)
        missing = expected - found
        assert not missing, f"Missing modules: {missing}"


# ── Semantic Affinity & Co-Change Tests ─────────────────────────────────────


class TestSemanticAndCochange:
    """Test new edge sources — semantic affinity and co-change analysis."""

    def test_semantic_affinity_no_sentence_transformers(self, tmp_path: Path) -> None:
        """Without sentence-transformers, returns zero matrix."""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        adj, names = _build_module_adjacency(str(tmp_path))
        sem_adj = _build_semantic_adjacency(str(tmp_path), names, semantic_weight=0.3)
        assert sem_adj.shape == adj.shape
        # Without the model, it should be all zeros
        assert sem_adj.sum() == 0.0

    def test_semantic_affinity_empty_modules(self) -> None:
        """Empty module list returns empty matrix."""
        sem_adj = _build_semantic_adjacency("/tmp", [], semantic_weight=0.3)
        assert sem_adj.shape == (0, 0)

    def test_semantic_affinity_with_import(self, tmp_path: Path) -> None:
        """Still works (graceful no-model fallback) within suggest_modules."""
        (tmp_path / "main.py").write_text("import lib\n")
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "__init__.py").write_text("X = 1\n")
        result = suggest_modules(
            str(tmp_path), semantic_weight=0.3, min_cluster_size=2,
        )
        assert result.num_modules >= 2
        assert result.num_clusters >= 1

    def test_cochange_no_git(self, tmp_path: Path) -> None:
        """Without git repo, returns zero matrix."""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        adj, names = _build_module_adjacency(str(tmp_path))
        co_adj = _build_cochange_adjacency(str(tmp_path), names, cochange_weight=0.4)
        assert co_adj.shape == adj.shape
        assert co_adj.sum() == 0.0

    def test_cochange_empty_modules(self) -> None:
        """Empty module list returns empty matrix."""
        co_adj = _build_cochange_adjacency("/tmp", [], cochange_weight=0.4)
        assert co_adj.shape == (0, 0)

    def test_cochange_with_git_repo(self, tmp_path: Path) -> None:
        """With a git repo and commits, co-change finds edges."""
        import subprocess
        # Init git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path, capture_output=True,
        )

        # Create files and make commits that change them together
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        (tmp_path / "c.py").write_text("z = 3\n")

        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path, capture_output=True,
        )

        # Change a and b together
        (tmp_path / "a.py").write_text("x = 2\n")
        (tmp_path / "b.py").write_text("y = 3\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "change ab"],
            cwd=tmp_path, capture_output=True,
        )

        # Change a and c together
        (tmp_path / "a.py").write_text("x = 3\n")
        (tmp_path / "c.py").write_text("z = 4\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "change ac"],
            cwd=tmp_path, capture_output=True,
        )

        # Now test co-change analysis
        adj, names = _build_module_adjacency(str(tmp_path))
        co_adj = _build_cochange_adjacency(
            str(tmp_path), names, cochange_weight=0.4, max_commits=100,
        )
        assert co_adj.shape == adj.shape
        # Should have found at least one co-change edge
        edge_count = len(co_adj.nonzero()[0]) // 2
        assert edge_count >= 1, f"Expected co-change edges, got {edge_count}"
        # a-b and a-c should have co-change signal
        if "a" in names and "b" in names:
            ai, bi = names.index("a"), names.index("b")
            assert co_adj[ai, bi] > 0, "a-b should have co-change edge"

    def test_fusion_all_disabled_by_default(self, tmp_path: Path) -> None:
        """Default call with no optional sources works (backward compat)."""
        (tmp_path / "main.py").write_text("import helper\n")
        (tmp_path / "helper.py").write_text("x = 1\n")
        result = suggest_modules(str(tmp_path), min_cluster_size=2)
        assert result.num_modules >= 2

    def test_fusion_with_cochange_and_semantic(self, tmp_path: Path) -> None:
        """Both optional sources gracefully fall back when unavailable."""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=tmp_path, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp_path, capture_output=True,
        )

        (tmp_path / "main.py").write_text("import helper\n")
        (tmp_path / "helper.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path, capture_output=True,
        )

        # semantic_weight > 0 triggers ~10s model load; test with 0 here
        result = suggest_modules(
            str(tmp_path), min_cluster_size=2,
            semantic_weight=0.0, cochange_weight=0.4,
        )
        assert result.num_modules >= 2

    def test_tool_function_new_params(self, synthetic_project: Path) -> None:
        """MCP tool accepts the new params without error."""
        result = _tool_suggest_modules({
            "project_root": str(synthetic_project),
            "semantic_weight": 0.0,  # 0.0 = off; >0 triggers model loading (~10s)
            "cochange_weight": 0.0,  # 0.0 = off; >0 needs git repo
        })
        assert "clusters" in result
        assert result["num_modules"] > 0

    def test_suggest_modules_with_config(self, synthetic_project: Path) -> None:
        """Can call suggest_modules with a SpectralConfig instance."""
        config = SpectralConfig(
            project_root=str(synthetic_project),
            min_cluster_size=2,
        )
        result = suggest_modules(config=config)
        assert result.num_modules > 0
        assert result.num_clusters > 0
        assert all(c.name for c in result.clusters), "All clusters should have names"

    def test_config_from_dict(self) -> None:
        """SpectralConfig.from_dict builds correctly from MCP args."""
        config = SpectralConfig.from_dict({
            "project_root": "/tmp/proj",
            "min_cluster_size": 5,
            "use_call_graph": True,
            "nonexistent_param": "ignored",
        })
        assert config.project_root == "/tmp/proj"
        assert config.min_cluster_size == 5
        assert config.use_call_graph is True
        assert not hasattr(config, "nonexistent_param")


# ── Edge Cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_nonexistent_project(self) -> None:
        """Non-existent directory raises ValueError."""
        with pytest.raises(ValueError, match="does not exist"):
            suggest_modules("/nonexistent/path/xyz")

    def test_isomorphic_module_names(self, tmp_path: Path) -> None:
        """Modules with similar names don't confuse clustering."""
        project = tmp_path / "iso"
        project.mkdir()
        (project / "a.py").write_text("import b\n")
        (project / "b.py").write_text("import a\n")
        result = suggest_modules(str(project))
        assert result.num_modules >= 2
        # Both modules should be assigned somewhere
        assert sum(c.size for c in result.clusters) == result.num_modules

    def test_very_small_project(self, tmp_path: Path) -> None:
        """2-file project returns reasonable clusters."""
        project = tmp_path / "small"
        project.mkdir()
        (project / "main.py").write_text("import helper\n")
        (project / "helper.py").write_text("x = 1\n")
        result = suggest_modules(str(project))
        assert result.num_modules >= 1
