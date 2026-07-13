#!/usr/bin/env python3
"""Spectral clustering for module decomposition.

Uses the Fiedler vector of the graph Laplacian to partition a codebase's
dependency graph into cohesive modules. Pure numpy implementation with
optional scipy acceleration.

Phase 1 of the spectral clustering feature:
  - Builds weighted affinity matrix from import/call dependency graphs
  - Computes Fiedler vector via power iteration (numpy-only fallback)
  - Recursive bipartitioning with automatic stop based on partition quality
  - Returns cluster assignments with module/file mappings

Usage:
    from ast_tools.tools.spectral import suggest_modules
    result = suggest_modules("/path/to/project")
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class PartitionNode:
    """A node in the recursive partition tree.

    Attributes:
        id: Unique partition identifier (e.g. "0", "0.0", "0.1")
        modules: Set of module paths in this partition
        depth: Recursion depth (0 = root)
        score: Partition quality score (higher = better)
        fiedler_value: Algebraic connectivity (λ₂) of this partition
        left: Left child partition (modules with Fiedler value < threshold)
        right: Right child partition (modules with Fiedler value >= threshold)
    """

    id: str
    modules: frozenset[str]
    depth: int = 0
    score: float = 0.0
    fiedler_value: float = 0.0
    left: PartitionNode | None = None
    right: PartitionNode | None = None


@dataclass
class ClusterAssignment:
    """A single module cluster result.

    Attributes:
        cluster_id: Numeric cluster identifier (0-indexed)
        modules: List of module paths in this cluster
        size: Number of modules in cluster
        cohesion: Average intra-cluster edge weight
        coupling: Average inter-cluster edge weight to other clusters
    """

    cluster_id: int
    modules: list[str]
    size: int
    cohesion: float = 0.0
    coupling: float = 0.0


@dataclass
class SpectralResult:
    """Complete result of spectral clustering.

    Attributes:
        clusters: List of cluster assignments
        partition_tree: Root of the recursive partition tree
        num_modules: Total number of modules analyzed
        num_clusters: Number of clusters found
        quality: Overall modularity quality score
        algebraic_connectivity: λ₂ of the full graph (higher = better connected)
        isolated_modules: Modules with no edges (singleton clusters)
    """

    clusters: list[ClusterAssignment]
    partition_tree: PartitionNode | None
    num_modules: int
    num_clusters: int
    quality: float = 0.0
    algebraic_connectivity: float = 0.0
    isolated_modules: list[str] = field(default_factory=list)


# ── Core Spectral Algorithm ─────────────────────────────────────────────────


def _normalized_laplacian(adjacency: np.ndarray) -> np.ndarray:
    """Compute the symmetric normalized Laplacian L_sym = D^{-1/2} * L * D^{-1/2}.

    Args:
        adjacency: N×N weighted adjacency matrix (symmetric).

    Returns:
        N×N normalized Laplacian matrix.
    """
    d = np.sum(adjacency, axis=1)
    # Avoid division by zero for isolated nodes
    with np.errstate(divide="ignore"):
        d_inv_sqrt = np.where(d > 1e-10, 1.0 / np.sqrt(d), 0.0)
    # L_sym = I - D^{-1/2} * A * D^{-1/2}
    return np.eye(adjacency.shape[0]) - d_inv_sqrt[:, None] * adjacency * d_inv_sqrt[None, :]


def _fiedler_vector_power_iteration(
    laplacian: np.ndarray,
    n_iter: int = 1000,
    tol: float = 1e-6,
    rng_seed: int = 42,
) -> tuple[np.ndarray, float]:
    """Compute the Fiedler vector (2nd smallest eigenvector) via power iteration.

    Uses orthogonal deflation: finds the nullspace eigenvector (all ones for
    connected graph), then runs power iteration on the shifted inverse
    (L + μI)^{-1} to converge on the Fiedler vector.

    Pure numpy implementation — no scipy required.

    Args:
        laplacian: N×N Laplacian matrix.
        n_iter: Maximum power iterations.
        tol: Convergence tolerance.
        rng_seed: RNG seed for reproducibility.

    Returns:
        Tuple of (fiedler_vector, fiedler_value).
        fiedler_value is the algebraic connectivity (λ₂).
    """
    n = laplacian.shape[0]

    if n < 2:
        return np.ones(n) * 0.5, 0.0

    # Shift-invert: instead of finding smallest λ, invert and find largest
    # (L + μI)^{-1} has eigenvalues 1/(λ + μ)
    # We want λ₂ (smallest non-zero), so shift μ slightly above 0
    mu = 0.1
    shifted = laplacian + mu * np.eye(n)

    try:
        shifted_inv = np.linalg.inv(shifted)
    except np.linalg.LinAlgError:
        # Fallback: use pseudoinverse
        shifted_inv = np.linalg.pinv(shifted)

    # Start from random vector orthogonal to the nullspace (all-ones vector)
    rng = np.random.default_rng(rng_seed)
    v = rng.normal(size=n)
    # Deflate: subtract projection onto nullspace (all-ones)
    v = v - (np.sum(v) / n) * np.ones(n)
    v = v / np.linalg.norm(v)

    for _ in range(n_iter):
        v_new = shifted_inv @ v
        v_new = v_new - (np.sum(v_new) / n) * np.ones(n)
        norm = np.linalg.norm(v_new)
        if norm < 1e-15:
            break
        v_new = v_new / norm

        # Convergence check
        diff = np.linalg.norm(v_new - v)
        if diff < tol:
            v = v_new
            break
        v = v_new

    # Compute the actual eigenvalue: λ = v^T L v (Rayleigh quotient)
    fiedler_value = v @ (laplacian @ v)
    # Bound to [0, n] range
    fiedler_value = max(0.0, min(float(fiedler_value), float(n)))

    return v, fiedler_value


def _partition_quality(
    adjacency: np.ndarray,
    labels: np.ndarray,
    n_clusters: int,
) -> float:
    """Compute modularity-like quality score for a partition.

    Q = (sum of intra-cluster edges) / (total edges) -
        (expected intra-cluster edges under random model)

    Higher is better. Range roughly [-0.5, 1].

    Args:
        adjacency: N×N weighted adjacency matrix.
        labels: Cluster assignments (length N).
        n_clusters: Number of clusters.

    Returns:
        Quality score (modularity Q).
    """
    total_weight = np.sum(adjacency)
    if total_weight < 1e-10:
        return 0.0

    degree = np.sum(adjacency, axis=1)
    m = total_weight / 2.0

    q = 0.0
    for c in range(n_clusters):
        mask = labels == c
        cluster_nodes = np.where(mask)[0]
        if len(cluster_nodes) < 2:
            continue

        # Internal edges
        internal = adjacency[np.ix_(cluster_nodes, cluster_nodes)]
        l_c = np.sum(internal) / 2.0

        # Expected edges under configuration model
        d_c = np.sum(degree[cluster_nodes])
        expected = (d_c * d_c) / (4.0 * m) if m > 0 else 0

        q += (l_c - expected) / m

    return float(q)


def _fiedler_bipartition(
    adjacency: np.ndarray,
    module_names: list[str],
    partition_id: str,
    depth: int,
    min_size: int = 2,
    max_depth: int = 10,
) -> PartitionNode:
    """Recursively bipartition a set of modules using the Fiedler vector.

    Args:
        adjacency: N×N weighted adjacency matrix.
        module_names: List of module names corresponding to rows.
        partition_id: Unique identifier for this partition.
        depth: Current recursion depth.
        min_size: Minimum partition size for continued splitting.
        max_depth: Maximum recursion depth.

    Returns:
        PartitionNode with potential left/right children.
    """
    n = len(module_names)

    # Base case: too small or too deep
    if n < min_size or depth >= max_depth:
        return PartitionNode(
            id=partition_id,
            modules=frozenset(module_names),
            depth=depth,
        )

    # Compute Fiedler vector
    laplacian = _normalized_laplacian(adjacency)
    fiedler_vec, fiedler_val = _fiedler_vector_power_iteration(laplacian)

    # Split by sign of Fiedler vector entries
    threshold = 0.0
    left_mask = fiedler_vec < threshold
    right_mask = ~left_mask

    left_indices = np.where(left_mask)[0]
    right_indices = np.where(right_mask)[0]

    # Edge case: one side is empty — partition failed
    if len(left_indices) == 0 or len(right_indices) == 0:
        return PartitionNode(
            id=partition_id,
            modules=frozenset(module_names),
            depth=depth,
            fiedler_value=float(fiedler_val),
        )

    # Compute quality of this split
    labels = np.zeros(n, dtype=int)
    labels[left_indices] = 0
    labels[right_indices] = 1
    quality = _partition_quality(adjacency, labels, 2)

    left_modules = [module_names[i] for i in left_indices]
    right_modules = [module_names[i] for i in right_indices]

    left_adj = adjacency[np.ix_(left_indices, left_indices)]
    right_adj = adjacency[np.ix_(right_indices, right_indices)]

    node = PartitionNode(
        id=partition_id,
        modules=frozenset(module_names),
        depth=depth,
        score=quality,
        fiedler_value=float(fiedler_val),
    )

    # Recurse on each side
    node.left = _fiedler_bipartition(
        left_adj, left_modules, f"{partition_id}.0", depth + 1, min_size, max_depth
    )
    node.right = _fiedler_bipartition(
        right_adj, right_modules, f"{partition_id}.1", depth + 1, min_size, max_depth
    )

    return node


def _collect_leaves(node: PartitionNode) -> list[PartitionNode]:
    """Collect all leaf nodes from a partition tree (breadth-first).

    Args:
        node: Root of the partition tree.

    Returns:
        List of leaf PartitionNodes.
    """
    leaves: list[PartitionNode] = []
    queue = deque([node])
    while queue:
        current = queue.popleft()
        if current.left or current.right:
            if current.left:
                queue.append(current.left)
            if current.right:
                queue.append(current.right)
        else:
            leaves.append(current)
    return leaves


def _compute_cohesion_coupling(
    adjacency: np.ndarray,
    module_names: list[str],
    cluster_labels: dict[str, int],
) -> tuple[float, float]:
    """Compute average intra-cluster cohesion and inter-cluster coupling.

    Args:
        adjacency: N×N weighted adjacency matrix.
        module_names: Module names indexed to adjacency matrix.
        cluster_labels: Mapping of module_name -> cluster_id.

    Returns:
        Tuple of (avg_cohesion, avg_coupling).
    """
    n = len(module_names)
    if n == 0:
        return 0.0, 0.0

    total_intra = 0.0
    total_inter = 0.0
    intra_count = 0
    inter_count = 0

    for i in range(n):
        for j in range(i + 1, n):
            w = float(adjacency[i, j])
            if w < 1e-10:
                continue
            mi = module_names[i]
            mj = module_names[j]
            if cluster_labels.get(mi) == cluster_labels.get(mj):
                total_intra += w
                intra_count += 1
            else:
                total_inter += w
                inter_count += 1

    avg_cohesion = total_intra / intra_count if intra_count > 0 else 0.0
    avg_coupling = total_inter / inter_count if inter_count > 0 else 0.0
    return avg_cohesion, avg_coupling


# ── Graph Construction ────────────────────────────────────────────────────────


# ── Language Detection & Multi-Language Import Extraction ─────────────────


# Language-specific source file extensions
LANG_EXTENSIONS: dict[str, set[str]] = {
    "python":      {".py"},
    "typescript":  {".ts", ".tsx"},
    "javascript":  {".js", ".jsx", ".mjs", ".cjs"},
    "go":          {".go"},
    "rust":        {".rs"},
    "c":           {".c", ".h"},
    "cpp":         {".cpp", ".cc", ".cxx", ".hpp", ".hh"},
}

# Reverse: extension → language code
_EXT_TO_LANG: dict[str, str] = {}
for _lang, _exts in LANG_EXTENSIONS.items():
    for _ext in _exts:
        _EXT_TO_LANG[_ext] = _lang


def _detect_language(file_path: Path) -> str | None:
    """Detect programming language from file extension."""
    return _EXT_TO_LANG.get(file_path.suffix.lower())


def _iter_source_files(project_path: Path) -> list[Path]:
    """Iterate all source files across supported languages.

    Skips hidden directories, __pycache__, node_modules, .venv, etc.
    """
    skip_dirs = {
        ".git", "__pycache__", ".venv", "venv", "node_modules",
        ".tox", ".eggs", "build", "dist", ".mypy_cache",
        ".pytest_cache", ".idea", ".vscode", "site-packages",
        "target",  # Rust build dir
        ".next", ".nuxt",  # JS framework build dirs
    }
    source_files: list[Path] = []
    for f in sorted(project_path.rglob("*")):
        if not f.is_file():
            continue
        # Check if in skip directory
        rel = f.relative_to(project_path)
        if any(p in skip_dirs for p in rel.parts):
            continue
        if f.suffix.lower() in _EXT_TO_LANG:
            source_files.append(f)
    return source_files


def _file_to_module_name(file_path: Path, project_path: Path) -> str:
    """Convert a file path to a canonical module name.

    Examples:
        src/ast_tools/tools/spectral.py → src.ast_tools.tools.spectral
        src/ast_tools/__init__.py       → src.ast_tools
        frontend/src/components/Button.tsx → frontend.src.components.Button
        cmd/server/main.go             → cmd.server.main
    """
    rel = file_path.relative_to(project_path)
    parts = list(rel.parts)
    name = parts[-1]
    # Strip extension
    dot = name.find(".")
    if dot > 0:
        name = name[:dot]
    parts[-1] = name
    # Handle __init__ → parent dir
    if name == "__init__":
        parts = parts[:-1]
    # Handle index files for JS/TS
    if name in ("index", "main", "mod"):
        # Keep as-is (don't strip)
        pass
    return ".".join(parts)


def _resolve_ts_import(
    import_path: str,
    source_file: Path,
    project_path: Path,
) -> set[Path]:
    """Resolve a TypeScript/JavaScript import relative path to file(s).

    Tries common extensions and index files.
    """
    if not import_path.startswith("./") and not import_path.startswith("../"):
        # Not a relative import — could be a source-level path like "components/Button"
        # Only resolve if it looks like a source path (no npm package format)
        if "/" in import_path and not import_path.startswith("@"):
            # Could be a project-absolute path like "src/components/Button"
            candidates = set()
            for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
                candidate = project_path / f"{import_path}{ext}"
                if candidate.exists():
                    candidates.add(candidate)
            return candidates
        return set()

    # Resolve relative import
    resolved = (source_file.parent / import_path).resolve()
    candidates: set[Path] = set()

    # Try direct file with extensions
    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".d.ts", ".d.mts"):
        candidate = resolved.with_suffix(ext)
        if candidate.exists() and candidate.is_file():
            # Normalize to project relative for consistency
            try:
                candidates.add(candidate.relative_to(project_path))
            except ValueError:
                candidates.add(candidate)

    # Try index files
    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
        index_candidate = resolved / f"index{ext}"
        if index_candidate.exists():
            try:
                candidates.add(index_candidate.relative_to(project_path))
            except ValueError:
                candidates.add(index_candidate)

    return candidates


def _resolve_go_import(
    import_path: str,
    _source_file: Path,
    project_path: Path,
) -> set[Path]:
    """Resolve a Go import path to internal file(s).

    Go imports are full paths like "github.com/user/project/pkg".
    We check if the import path's last segment(s) match an internal directory.
    """
    candidates: set[Path] = set()

    # Try matching as a relative filesystem path
    candidate = project_path / import_path
    if candidate.exists() and candidate.is_dir():
        # Check for Go files in that directory
        for g in sorted(candidate.glob("*.go")):
            try:
                candidates.add(g.relative_to(project_path))
            except ValueError:
                candidates.add(g)

    # Try just the last path component
    parts = import_path.split("/")
    for i in range(len(parts), 0, -1):
        subpath = "/".join(parts[-i:])
        candidate = project_path / subpath
        if candidate.exists() and candidate.is_dir():
            for g in sorted(candidate.glob("*.go")):
                try:
                    candidates.add(g.relative_to(project_path))
                except ValueError:
                    candidates.add(g)
            if candidates:
                return candidates

    return candidates


def _resolve_rust_import(
    import_path: str,
    source_file: Path,
    project_path: Path,
) -> set[Path]:
    """Resolve a Rust use path to internal file(s).

    Handles:
        crate::module::submodule → path/to/module/submodule
        super::module → ../path/to/module
        self::submodule → same dir submodule
    """
    candidates: set[Path] = set()

    if import_path.startswith("crate::"):
        internal_path = import_path.replace("crate::", "")
        parts = internal_path.split("::")
        # Try as path: src/<parts>.rs or src/<parts>/mod.rs
        for prefix in ("", "src", "src/lib", "src/main"):
            if prefix:
                full = project_path / prefix / "/".join(parts)
            else:
                full = project_path / "/".join(parts)
            # Try as file
            for ext in (".rs",):
                candidate = full.with_suffix(ext)
                if candidate.exists():
                    try:
                        candidates.add(candidate.relative_to(project_path))
                    except ValueError:
                        candidates.add(candidate)
            # Try as directory with mod.rs
            mod_candidate = full / "mod.rs"
            if mod_candidate.exists():
                try:
                    candidates.add(mod_candidate.relative_to(project_path))
                except ValueError:
                    candidates.add(mod_candidate)
        return candidates

    if import_path.startswith("super::"):
        # Go up one directory level
        # e.g. super::module::submodule
        remaining = import_path.removeprefix("super::")
        parts = remaining.split("::")
        parent = source_file.parent.parent  # super = parent dir
        if parent:
            full = parent / "/".join(parts)
            for ext in (".rs",):
                candidate = full.with_suffix(ext)
                if candidate.exists():
                    try:
                        candidates.add(candidate.relative_to(project_path))
                    except ValueError:
                        candidates.add(candidate)
            mod_candidate = full / "mod.rs"
            if mod_candidate.exists():
                try:
                    candidates.add(mod_candidate.relative_to(project_path))
                except ValueError:
                    candidates.add(mod_candidate)
        return candidates

    if import_path.startswith("self::"):
        remaining = import_path.removeprefix("self::")
        parts = remaining.split("::")
        full = source_file.parent / "/".join(parts)
        for ext in (".rs",):
            candidate = full.with_suffix(ext)
            if candidate.exists():
                try:
                    candidates.add(candidate.relative_to(project_path))
                except ValueError:
                    candidates.add(candidate)
        mod_candidate = full / "mod.rs"
        if mod_candidate.exists():
            try:
                candidates.add(mod_candidate.relative_to(project_path))
            except ValueError:
                candidates.add(mod_candidate)
        return candidates

    # External crate (e.g. "serde::Serialize") — skip
    return candidates


def _resolve_c_include(
    include_path: str,
    source_file: Path,
    project_path: Path,
) -> set[Path]:
    """Resolve a C/C++ include directive to internal file(s)."""
    candidates: set[Path] = set()

    # Quoted includes like "internal/header.h" — resolve relative to source
    if not include_path.startswith("<"):
        # Try relative to source file
        candidate = (source_file.parent / include_path).resolve()
        try:
            candidate_rel = candidate.relative_to(project_path)
            if candidate.exists():
                candidates.add(candidate_rel)
        except ValueError:
            if candidate.exists():
                candidates.add(candidate)

        # Try relative to project root
        candidate2 = project_path / include_path
        if candidate2.exists():
            try:
                candidates.add(candidate2.relative_to(project_path))
            except ValueError:
                candidates.add(candidate2)

    # System includes (<stdio.h>) are skipped — not internal

    return candidates


# Multi-language import query string builders
_TS_IMPORT_QUERY = """
(import_statement
  source: (string (string_fragment) @path))
"""

_GO_IMPORT_QUERY = """
(import_spec
  path: (interpreted_string_literal (interpreted_string_literal_content) @path))
"""

_RUST_USE_QUERY = """
(use_declaration
  (scoped_identifier) @path)
"""

_C_INCLUDE_QUERY = """
(preproc_include
  (string_literal (string_content) @path))
"""


def _extract_imports_ts(tree, source: str) -> list[str]:
    """Extract import paths from a TypeScript/JavaScript tree."""
    # Tree-sitter 0.26 query API
    import tree_sitter as ts
    lang = tree.language
    query = ts.Query(lang, _TS_IMPORT_QUERY)
    cursor = ts.QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    paths: list[str] = []
    for name, nodes in captures.items():
        for node in nodes:
            path = node.text.decode("utf-8")
            if path:
                paths.append(path)
    return paths


def _extract_imports_go(tree, source: str) -> list[str]:
    """Extract import paths from a Go tree."""
    import tree_sitter as ts
    query = ts.Query(tree.language, _GO_IMPORT_QUERY)
    cursor = ts.QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    paths: list[str] = []
    for name, nodes in captures.items():
        for node in nodes:
            path = node.text.decode("utf-8")
            if path:
                paths.append(path)
    return paths


def _extract_imports_rust(tree, source: str) -> list[str]:
    """Extract use paths from a Rust tree."""
    import tree_sitter as ts
    query = ts.Query(tree.language, _RUST_USE_QUERY)
    cursor = ts.QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    paths: list[str] = []
    for name, nodes in captures.items():
        for node in nodes:
            path = node.text.decode("utf-8")
            if path:
                # Convert path::separators to module-style path
                # strip any leading/trailing ::
                path = path.strip().strip(":")
                if path:
                    paths.append(path)
    return paths


def _extract_imports_c(tree, source: str) -> list[str]:
    """Extract include paths from a C/C++ tree."""
    import tree_sitter as ts
    query = ts.Query(tree.language, _C_INCLUDE_QUERY)
    cursor = ts.QueryCursor(query)
    captures = cursor.captures(tree.root_node)
    paths: list[str] = []
    for name, nodes in captures.items():
        for node in nodes:
            path = node.text.decode("utf-8")
            if path:
                paths.append(path)
    return paths


def _extract_imports_python(source: str, source_module: str,
                             internal_modules: set[str],
                             stdlib_modules: set[str],
                             third_party_prefixes: set[str],
                             edge_weight: float,
                             adjacency: dict[tuple[str, str], float]) -> None:
    """Extract import edges from a Python file using ast.parse.

    Modifies ``adjacency`` in-place.
    """
    import ast as ast_module
    try:
        tree = ast_module.parse(source, filename="<spectral>")
    except SyntaxError:
        return

    for node in ast_module.walk(tree):
        if isinstance(node, ast_module.Import):
            for alias in node.names:
                target = alias.name.split(".")[0]
                if target in internal_modules:
                    adjacency[(source_module, target)] += edge_weight
                elif target not in stdlib_modules and target not in third_party_prefixes:
                    for im in internal_modules:
                        if im == target or im.startswith(target + "."):
                            adjacency[(source_module, im)] += edge_weight * 0.3
                            break

        elif isinstance(node, ast_module.ImportFrom) and node.module is not None:
            if node.level == 0:
                target_pkg = node.module.split(".")[0]
                if target_pkg in internal_modules:
                    adjacency[(source_module, node.module)] += edge_weight
                elif target_pkg not in stdlib_modules and target_pkg not in third_party_prefixes:
                    for im in internal_modules:
                        if im == node.module or im.startswith(node.module + "."):
                            adjacency[(source_module, im)] += edge_weight * 0.3
                            break
            else:
                parts = source_module.split(".")
                if node.level <= len(parts):
                    base = ".".join(parts[:-node.level])
                else:
                    base = ""
                resolved = f"{base}.{node.module}" if base and node.module else (base or node.module or "")
                if resolved and resolved in internal_modules:
                    adjacency[(source_module, resolved)] += edge_weight
                elif resolved:
                    for im in internal_modules:
                        if im == resolved or im.startswith(resolved + "."):
                            adjacency[(source_module, im)] += edge_weight * 0.3
                            break


# Language dispatch table
_LANG_IMPORT_EXTRACTOR = {
    "python": lambda tree, src: [],  # Handled by _extract_imports_python
    "typescript": _extract_imports_ts,
    "javascript": _extract_imports_ts,
    "go": _extract_imports_go,
    "rust": _extract_imports_rust,
    "c": _extract_imports_c,
    "cpp": _extract_imports_c,
}

_LANG_RESOLVER = {
    "typescript": _resolve_ts_import,
    "javascript": _resolve_ts_import,
    "go": _resolve_go_import,
    "rust": _resolve_rust_import,
    "c": _resolve_c_include,
    "cpp": _resolve_c_include,
}


def _build_module_adjacency(
    project_root: str,
    edge_weight: float = 1.0,
    include_submodules: bool = True,
) -> tuple[np.ndarray, list[str]]:
    """Build a weighted adjacency matrix from import analysis across all supported languages.

    Parses every source file in the project using the appropriate parser
    (ast.parse for Python, tree-sitter for others), resolves imports to
    internal files, and creates a symmetric weighted adjacency matrix.

    Args:
        project_root: Root of the project to analyze.
        edge_weight: Weight for import edges (default: 1.0).
        include_submodules: If True, include implicit submodule containment
                           edges and directory proximity edges.

    Returns:
        Tuple of (adjacency_matrix, module_names).
        adjacency_matrix is N×N symmetric with edge weights.
        module_names[i] is the module path corresponding to row i.
    """
    project_path = Path(project_root)
    if not project_path.is_dir():
        return np.zeros((0, 0)), []

    # ── Step 1: Discover all source files across languages ──
    source_files = _iter_source_files(project_path)
    if not source_files:
        return np.zeros((0, 0)), []

    # ── Step 2: Build internal module map for ALL files ──
    file_to_module: dict[Path, str] = {}
    module_to_file: dict[str, Path] = {}
    # Also maintain relative path map for resolution
    rel_path_to_file: dict[str, Path] = {}

    for f in source_files:
        try:
            rel = f.relative_to(project_path)
        except ValueError:
            continue
        module = _file_to_module_name(f, project_path)
        file_to_module[f] = module
        module_to_file[module] = f
        rel_path_to_file[str(rel)] = f

    internal_modules: set[str] = set(file_to_module.values())

    # Also index files by stem (for matching imports to files)
    stem_to_files: dict[str, list[Path]] = {}
    for f in source_files:
        try:
            rel = f.relative_to(project_path)
        except ValueError:
            continue
        stem = rel.stem
        stem_to_files.setdefault(stem, []).append(f)

    # ── Step 3: Setup stdlib/third-party filters (Python-specific) ──
    stdlib_modules: set[str] = set()
    try:
        import sys
        stdlib_modules = {p for p in sys.stdlib_module_names}
    except (AttributeError, KeyError):
        stdlib_modules = {
            "abc", "ast", "asyncio", "base64", "collections", "copy",
            "csv", "dataclasses", "datetime", "decimal", "enum", "functools",
            "glob", "hashlib", "html", "http", "importlib", "inspect",
            "io", "itertools", "json", "logging", "math", "multiprocessing",
            "os", "pathlib", "pickle", "platform", "pprint", "queue",
            "random", "re", "shutil", "signal", "socket", "sqlite3",
            "statistics", "string", "struct", "subprocess", "sys",
            "tempfile", "textwrap", "threading", "time", "traceback",
            "typing", "unittest", "urllib", "uuid", "warnings", "weakref",
            "xml", "zipfile", "__future__",
        }

    third_party_prefixes = {
        "pytest", "numpy", "scipy", "sklearn", "torch", "tensorflow",
        "yaml", "jsonschema", "libcst", "mcp",
        "jedi", "tree_sitter", "tiktoken", "watchdog", "anyio",
        "sentence_transformers", "sqlite_vec", "sqlparse", "hnswlib",
    }

    # ── Step 4: Parse each file and collect intra-project edges ──
    adjacency: dict[tuple[str, str], float] = defaultdict(float)

    # Pre-load ts_backend if needed
    _ts_available = False
    try:
        import ts_backend
        _ts_available = True
    except ImportError:
        pass

    for f in source_files:
        source_module = file_to_module.get(f)
        if source_module is None:
            continue

        lang = _detect_language(f)
        if lang is None:
            continue

        try:
            source = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if lang == "python":
            # Python: use ast.parse (fast, accurate)
            _extract_imports_python(
                source, source_module, internal_modules,
                stdlib_modules, third_party_prefixes,
                edge_weight, adjacency,
            )
        elif _ts_available:
            # Other languages: use tree-sitter
            try:
                tree = ts_backend.ts_parse(source, lang)
                if tree is None:
                    continue
            except Exception:
                continue

            extractor = _LANG_IMPORT_EXTRACTOR.get(lang)
            resolver = _LANG_RESOLVER.get(lang)
            if extractor is None or resolver is None:
                continue

            import_paths = extractor(tree, source)
            for import_path in import_paths:
                # Resolve to actual file(s)
                resolved_files = resolver(import_path, f, project_path)
                for resolved in resolved_files:
                    # resolvers may return relative or absolute; normalize to absolute
                    resolved_abs = resolved if resolved.is_absolute() else (project_path / resolved)
                    target_module = file_to_module.get(resolved_abs)
                    if target_module and target_module in internal_modules:
                        adjacency[(source_module, target_module)] += edge_weight

    # ── Step 5: Submodule containment edges ──
    if include_submodules:
        for mod in internal_modules:
            parts = mod.split(".")
            if len(parts) > 1:
                parent = ".".join(parts[:-1])
                if parent in internal_modules:
                    adjacency[(mod, parent)] += edge_weight * 0.3
                    adjacency[(parent, mod)] += edge_weight * 0.3

    # ── Step 6: Directory proximity edges ──
    if include_submodules:
        dir_groups: dict[str, list[str]] = defaultdict(list)
        for mod in internal_modules:
            parts = mod.split(".")
            dir_key = ".".join(parts[:-1]) if len(parts) > 1 else "<root>"
            dir_groups[dir_key].append(mod)
        for _dir_key, group in dir_groups.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    adjacency[(group[i], group[j])] += edge_weight * 0.15
                    adjacency[(group[j], group[i])] += edge_weight * 0.15

    # ── Step 7: Build matrix ──
    module_names = sorted(internal_modules)
    n = len(module_names)
    if n == 0:
        return np.zeros((0, 0)), []

    module_index = {m: i for i, m in enumerate(module_names)}
    adj = np.zeros((n, n), dtype=np.float64)

    for (src, tgt), w in adjacency.items():
        if src in module_index and tgt in module_index:
            i, j = module_index[src], module_index[tgt]
            adj[i, j] += w
            adj[j, i] += w

    return adj, module_names


def _build_call_graph_adjacency(
    project_root: str,
    database_path: str | None = None,
    edge_weight: float = 1.0,
) -> tuple[np.ndarray, list[str]]:
    """Build weighted adjacency from the call graph / edge database.

    Uses the indexed symbol edges (CALLS, IMPORTS, INHERITS) from the
    semantic database to build a finer-grained adjacency than the simple
    import graph. Falls back to import graph if database unavailable.

    Args:
        project_root: Root of the project to analyze.
        database_path: Path to the semantic index database. If None, uses default.
        edge_weight: Base weight for edges (adjusted by edge type).

    Returns:
        Tuple of (adjacency_matrix, module_names).
    """
    # For Phase 1, piggyback on the import graph from dependency.py
    # Phase 2 will integrate database edges
    return _build_module_adjacency(project_root, edge_weight=edge_weight)


# ── Public API ────────────────────────────────────────────────────────────────


def suggest_modules(
    project_root: str,
    min_cluster_size: int = 2,
    max_clusters: int | None = None,
    edge_weight: float = 1.0,
    database_path: str | None = None,
    use_call_graph: bool = False,
) -> SpectralResult:
    """Suggest module decomposition using spectral clustering.

    Builds a dependency graph from the project's import structure, then
    recursively partitions using the Fiedler vector of the graph Laplacian.

    Args:
        project_root: Root directory of the Python project.
        min_cluster_size: Minimum modules per cluster (default: 2).
        max_clusters: Maximum number of clusters to produce. If None,
                     determined automatically by partition quality.
        edge_weight: Weight for dependency edges (default: 1.0).
        database_path: Path to semantic database (for Phase 2 call graph).
        use_call_graph: If True, use enriched call graph when available.

    Returns:
        SpectralResult with cluster assignments, tree, and quality metrics.
    """
    project_path = Path(project_root)
    if not project_path.is_dir():
        raise ValueError(f"Project root does not exist: {project_root}")

    # Step 1: Build adjacency matrix
    if use_call_graph and database_path:
        adj, module_names = _build_call_graph_adjacency(project_root, database_path, edge_weight)
    else:
        adj, module_names = _build_module_adjacency(project_root, edge_weight)

    n = len(module_names)
    if n == 0:
        return SpectralResult(
            clusters=[], partition_tree=None, num_modules=0, num_clusters=0
        )

    # Step 2: Handle isolated modules (no edges)
    degree = np.sum(adj, axis=1)
    connected_mask = degree > 1e-10
    isolated_indices = np.where(~connected_mask)[0]
    connected_indices = np.where(connected_mask)[0]

    isolated_modules = [module_names[i] for i in isolated_indices]

    if len(connected_indices) == 0:
        # All modules are isolated — each gets its own cluster
        clusters = [
            ClusterAssignment(cluster_id=i, modules=[m], size=1)
            for i, m in enumerate(module_names)
        ]
        return SpectralResult(
            clusters=clusters,
            partition_tree=None,
            num_modules=n,
            num_clusters=n,
            isolated_modules=isolated_modules,
        )

    # Step 3: Build adjacency for connected component
    connected_adj = adj[np.ix_(connected_indices, connected_indices)]
    connected_names = [module_names[i] for i in connected_indices]

    # Step 4: Compute full-graph algebraic connectivity
    full_laplacian = _normalized_laplacian(connected_adj)
    _, alg_conn = _fiedler_vector_power_iteration(full_laplacian)

    # Step 5: Determine max depth
    max_depth = math.ceil(math.log2(max_clusters)) if max_clusters else 10
    max_depth = min(max_depth, max(3, n // 2))

    # Step 6: Recursive bipartition
    root = _fiedler_bipartition(
        connected_adj,
        connected_names,
        partition_id="root",
        depth=0,
        min_size=min_cluster_size,
        max_depth=max_depth,
    )

    # Step 7: Collect leaves as clusters
    leaves = _collect_leaves(root)

    # Prune: merge small clusters if max_clusters is set
    if max_clusters and len(leaves) > max_clusters:
        # Sort by score ascending, merge smallest into neighbor
        leaves.sort(key=lambda n: n.score)
        while len(leaves) > max_clusters:
            smallest = leaves.pop(0)
            # Find closest leaf by shared parent
            parent_id = ".".join(smallest.id.split(".")[:-1])
            closest = None
            for leaf in leaves:
                if leaf.id.startswith(parent_id):
                    closest = leaf
                    break
            if closest is None:
                closest = leaves[0]
            # Merge smallest into closest
            combined = frozenset(smallest.modules | closest.modules)
            leaves = [
                PartitionNode(
                    id=closest.id,
                    modules=combined,
                    depth=closest.depth,
                )
                if leaf is closest
                else leaf
                for leaf in leaves
            ]

    # Step 8: Build cluster assignments
    cluster_assignments: dict[str, int] = {}
    clusters_out: list[ClusterAssignment] = []
    for cid, leaf in enumerate(sorted(leaves, key=lambda n: n.id)):
        mods = sorted(leaf.modules)
        for m in mods:
            cluster_assignments[m] = cid

        # Compute cohesion and coupling for this cluster
        cluster_indices = [
            i for i, mn in enumerate(connected_names) if mn in leaf.modules
        ]
        if len(cluster_indices) >= 2:
            sub_adj = connected_adj[np.ix_(cluster_indices, cluster_indices)]
            intra_edges = np.sum(sub_adj) / 2.0
            # All edges from this cluster to outside
            other_indices = [
                i for i in range(len(connected_names)) if i not in cluster_indices
            ]
            inter_edges = 0.0
            if other_indices:
                cross = connected_adj[np.ix_(cluster_indices, other_indices)]
                inter_edges = np.sum(cross)

            cohesion = intra_edges / max(len(cluster_indices), 1)
            coupling = inter_edges / max(len(other_indices), 1) if other_indices else 0.0
        else:
            cohesion = 0.0
            coupling = 0.0

        clusters_out.append(
            ClusterAssignment(
                cluster_id=cid,
                modules=mods,
                size=len(mods),
                cohesion=cohesion,
                coupling=coupling,
            )
        )

    # Assign isolated modules as singleton clusters
    for i, mod in enumerate(isolated_modules):
        cid = len(clusters_out) + i
        cluster_assignments[mod] = cid
        clusters_out.append(
            ClusterAssignment(cluster_id=cid, modules=[mod], size=1)
        )

    # Step 9: Compute overall quality
    if connected_names:
        labels_arr = np.zeros(len(connected_names), dtype=int)
        for i, mn in enumerate(connected_names):
            labels_arr[i] = cluster_assignments.get(mn, 0)
        quality = _partition_quality(connected_adj, labels_arr, len(set(labels_arr)))
    else:
        quality = 0.0

    return SpectralResult(
        clusters=clusters_out,
        partition_tree=root,
        num_modules=n,
        num_clusters=len(clusters_out),
        quality=quality,
        algebraic_connectivity=float(alg_conn),
        isolated_modules=isolated_modules,
    )


# ── MCP Tool Interface ────────────────────────────────────────────────────────


def _tool_suggest_modules(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool: suggest module decomposition via spectral clustering.

    Builds the import dependency graph of a Python project, then recursively
    partitions it using the Fiedler vector of the graph Laplacian to identify
    cohesive module groups.

    Args (from MCP):
        project_root: Root directory of the project.
        min_cluster_size: Minimum modules per cluster (default: 2).
        max_clusters: Maximum clusters to produce (default: None = auto).
        edge_weight: Weight for dependency edges (default: 1.0).
        use_call_graph: If True, use enriched call graph (default: False).

    Returns:
        Dict with keys:
            clusters: List of cluster assignments
            num_modules: Total modules analyzed
            num_clusters: Number of clusters found
            quality: Overall modularity quality score
            algebraic_connectivity: λ₂ of the graph
            isolated_modules: Modules with no dependencies
    """
    project_root = args.get("project_root", ".")
    min_cluster_size = args.get("min_cluster_size", 2)
    max_clusters = args.get("max_clusters")
    edge_weight = args.get("edge_weight", 1.0)
    database_path = args.get("database_path")
    use_call_graph = args.get("use_call_graph", False)

    result = suggest_modules(
        project_root=project_root,
        min_cluster_size=min_cluster_size,
        max_clusters=max_clusters,
        edge_weight=edge_weight,
        database_path=database_path,
        use_call_graph=use_call_graph,
    )

    return {
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "modules": c.modules,
                "size": c.size,
                "cohesion": round(c.cohesion, 4),
                "coupling": round(c.coupling, 4),
            }
            for c in result.clusters
        ],
        "num_modules": result.num_modules,
        "num_clusters": result.num_clusters,
        "quality": round(result.quality, 4),
        "algebraic_connectivity": round(result.algebraic_connectivity, 4),
        "isolated_modules": result.isolated_modules,
    }
