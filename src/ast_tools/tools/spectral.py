#!/usr/bin/env python3
"""Spectral clustering for module decomposition.

Partitions a codebase's dependency graph into cohesive module groups using
the Fiedler vector (2nd eigenvector) of the normalized graph Laplacian.

━━━ Architecture Overview ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    suggest_modules(project_root, ...)
        │
        ├── _build_module_adjacency()        ← Import graph (7 languages)
        │     ├── ast.parse (Python)
        │     ├── tree-sitter (TS/JS/Go/Rust/C/C++)
        │     ├── directory proximity edges  (+0.15 weight)
        │     └── submodule containment      (+0.30 weight)
        │
        ├── _build_call_graph_adjacency()    ← DB symbol edges (optional)
        │     ├── calls=1.0, imports=0.7, inherits=0.5, instantiates=0.5
        │     └── falls back to import graph if no DB
        │
        ├── _build_semantic_adjacency()      ← Embedding similarity (optional)
        │     ├── all-MiniLM-L6-v2, 384-dim cosine similarity
        │     └── weight ~0.2-0.5, threshold >0.5
        │
        ├── _build_cochange_adjacency()      ← Git evolution (optional)
        │     ├── Jaccard on commit co-occurrence
        │     └── weight ~0.3-0.6, threshold >0.05
        │
        │   All enabled sources fused additively → one weighted adjacency
        │
        └── Recursive spectral partitioning
              ├── _normalized_laplacian()        ← L = I - D^{-1/2} A D^{-1/2}
              ├── _fiedler_vector_power_iteration() ← λ₂ eigenvector via pow iter
              ├── _fiedler_bipartition()         ← Recursive split by sign
              ├── _partition_quality()           ← Modularity Q scoring
              └── _collect_leaves()              ← Leaves = clusters

━━━ Edge Sources ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Source              | Default  | Recommended | Requires
  ─────────────────────|──────────|─────────────|──────────────────────────
  Import graph        |  1.0     | always on   | Nothing (ast.parse / ts)
  Call graph (DB)     |  1.0*    | on if DB    | ast_tools indexed DB
  Semantic affinity   |  0.0     | 0.2-0.5     | sentence-transformers
  Co-change (git)     |  0.0     | 0.3-0.6     | git history
  Submodule contain   |  0.3     | always on   | Nothing
  Directory proximity |  0.15    | always on   | Nothing

  * Per edge type: calls=1.0, imports=0.7, inherits=0.5, instantiates=0.5

━━━ Function Map ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Public:
    suggest_modules(project_root, ...)        Main entry point
    _tool_suggest_modules(args)               MCP tool wrapper

  Core Algorithm:
    _normalized_laplacian(adj)                L = I - D^{-1/2} A D^{-1/2}
    _fiedler_vector_power_iteration(L)        Power iteration for λ₂
    _fiedler_bipartition(...)                 Recursive binary split
    _partition_quality(adj, labels, k)        Modularity Q (Newman-Girvan)

  Graph Construction:
    _build_module_adjacency(root)             Multi-language import graph
    _build_call_graph_adjacency(...)          DB-backed symbol edges
    _build_semantic_adjacency(...)            Embedding cosine similarity
    _build_cochange_adjacency(...)            Git co-occurrence Jaccard

  Utilities:
    _file_to_module_name(path, root)          File path → dot.module.name
    _filepath_to_module(path, root)           DB file path → module name
    _name_to_modules(name, root)              Symbol name → module candidates
    _iter_source_files(root)                  Discover all source files
    _detect_language(path)                    Extension → language
    _derive_cluster_name(modules)             Common prefix → cluster name
    _assign_cluster_names(clusters)           Disambiguate duplicate names

  Language-Specific Import Extraction:
    _extract_imports_python(...)              ast.parse (stdlib)
    _extract_imports_ts(tree)                 TS/JS tree-sitter query
    _extract_imports_go(tree)                 Go tree-sitter query
    _extract_imports_rust(tree)               Rust tree-sitter query
    _extract_imports_c(tree)                  C/C++ tree-sitter query
    _resolve_ts_import(...)                   TS/JS path resolution
    _resolve_go_import(...)                   Go path resolution
    _resolve_rust_import(...)                 Rust path resolution
    _resolve_c_include(...)                   C/C++ include resolution

━━━ Usage ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Basic: import graph only
    result = suggest_modules("src/ast_tools")

    # With all signals
    result = suggest_modules(
        "src/ast_tools",
        use_call_graph=True,     # DB symbol edges (auto fallback)
        semantic_weight=0.3,     # embedding cosine sim
        cochange_weight=0.4,     # git co-change Jaccard
    )

    # Via MCP tool
    _tool_suggest_modules({
        "project_root": "src/ast_tools",
        "min_cluster_size": 3,
        "use_call_graph": True,
    })

━━━ Dependencies ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Core:      numpy
  Optional:  scipy (for eigsh on >1000 node graphs)
  Optional:  tree-sitter + grammars (for non-Python import extraction)
  Optional:  sentence-transformers (for semantic affinity)
  Optional:  sqlite3 (stdlib, for call graph DB queries)

━━━ Data Structures ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  SpectralResult    ─ Top-level: clusters, tree, quality, connectivity
  SpectralConfig    ─ Configuration: project_root, weights, edge sources
  ClusterAssignment ─ A single cluster: id, name, modules, cohesion, coupling
  PartitionNode     ─ Binary tree node: id, modules, left, right, score
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# Scipy availability for sparse eigensolver (eigsh)
try:
    import scipy  # noqa: F401
    from scipy.sparse import csr_matrix
    from scipy.sparse.linalg import eigsh as scipy_eigsh
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    csr_matrix = None  # type: ignore

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
        name: Descriptive cluster name derived from common module prefix
        modules: List of module paths in this cluster
        size: Number of modules in cluster
        cohesion: Average intra-cluster edge weight
        coupling: Average inter-cluster edge weight to other clusters
    """

    cluster_id: int
    modules: list[str]
    size: int
    name: str = ""
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


@dataclass
class SpectralConfig:
    """Configuration for spectral clustering.

    Encapsulates all parameters for ``suggest_modules`` in a single dataclass,
    making the API extensible and self-documenting.

    Edge sources:
        - **Import graph** (always on): parses source files across 7 languages
          using ast.parse (Python) or tree-sitter (TS/JS/Go/Rust/C/C++).
        - **Call graph** (optional): resolves symbol-level edges (CALLS, IMPORTS,
          INHERITS, INSTANTIATES) from the ast-tools semantic database. Falls
          back to import graph if no database found.
        - **Semantic affinity** (optional): cosine similarity between per-module
          source embeddings (all-MiniLM-L6-v2, 384-dim). Edges added above a
          0.5 cosine threshold. Requires sentence-transformers.
        - **Co-change** (optional): Jaccard similarity on git commit co-occurrence.
          Analyzes the last ``max_commits`` modifications. Requires git history.

    Attributes:
        project_root: Root directory of the project to analyze (required).
        min_cluster_size: Minimum modules per cluster (default: 2).
        max_clusters: Maximum clusters (None = auto-determined by quality).
        edge_weight: Base weight for import edges (default: 1.0).
        database_path: Path to semantic DB for call graph (auto-detected if None).
        use_call_graph: If True, enrich with DB symbol edges (default: False).
        semantic_weight: Weight for embedding similarity edges. 0 = off.
            Recommended: 0.2–0.5.
        cochange_weight: Weight for git co-change edges. 0 = off.
            Recommended: 0.3–0.6.
        max_commits: Max git commits to scan for co-change (default: 1000).
    """

    project_root: str
    min_cluster_size: int = 2
    max_clusters: int | None = None
    edge_weight: float = 1.0
    database_path: str | None = None
    use_call_graph: bool = False
    semantic_weight: float = 0.0
    cochange_weight: float = 0.0
    max_commits: int = 1000

    @classmethod
    def from_dict(cls, args: dict[str, Any]) -> SpectralConfig:
        """Build a config from an MCP-style dict (ignores unknown keys).

        Args:
            args: Dict with keys matching SpectralConfig field names.

        Returns:
            SpectralConfig instance.
        """
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in args.items() if k in valid_keys}
        return cls(**filtered)


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


def _fiedler_vector_scalable(
    laplacian: np.ndarray,
    n: int,
    n_iter: int = 1000,
    tol: float = 1e-6,
    rng_seed: int = 42,
) -> tuple[np.ndarray, float]:
    """Compute Fiedler vector using the best available method.

    Uses scipy.sparse.linalg.eigsh (Lanczos) for large graphs (n >= 500),
    falls back to power iteration for smaller graphs or when scipy unavailable.

    Args:
        laplacian: N×N Laplacian matrix (dense numpy).
        n: Number of nodes.
        n_iter: Maximum iterations.
        tol: Convergence tolerance.
        rng_seed: RNG seed for power iteration fallback.

    Returns:
        Tuple of (fiedler_vector, fiedler_value).
    """
    # Small graphs or no scipy → use existing power iteration
    if n < 500 or not SCIPY_AVAILABLE:
        return _fiedler_vector_power_iteration(laplacian, n_iter, tol, rng_seed)

    # Large graph with scipy → use sparse eigsh (Lanczos)
    try:
        sparse_L = csr_matrix(laplacian)
        # Find 2 smallest eigenvalues (k=2 → λ₁ ≈ 0, λ₂ = Fiedler)
        eigenvalues, eigenvectors = scipy_eigsh(
            sparse_L, k=2, which="SM", tol=tol, maxiter=n_iter, v0=None,
        )
        # Sort ascending (eigsh doesn't guarantee order for SM)
        idx = np.argsort(eigenvalues)
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        fiedler_vec = eigenvectors[:, 1]
        fiedler_val = float(eigenvalues[1])
        # Bound
        fiedler_val = max(0.0, min(fiedler_val, float(n)))
        return fiedler_vec, fiedler_val
    except Exception as e:
        logger.warning(f"scipy eigsh failed ({e}), falling back to power iteration")
        return _fiedler_vector_power_iteration(laplacian, n_iter, tol, rng_seed)


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

    # Compute Fiedler vector using scalable method
    laplacian = _normalized_laplacian(adjacency)
    fiedler_vec, fiedler_val = _fiedler_vector_scalable(laplacian, n)

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

    Go imports are full paths like "github.com/user/project/pkg" or
    "module_name/internal/pkg". We check if the import path's last segment(s)
    match an internal directory. We also try stripping the first component
    (module name) to handle module paths like "testproj/internal/db".
    """
    candidates: set[Path] = set()

    # Try 1: Direct match (for non-module or same-module imports)
    candidate = project_path / import_path
    if candidate.exists() and candidate.is_dir():
        for g in sorted(candidate.glob("*.go")):
            try:
                candidates.add(g.relative_to(project_path))
            except ValueError:
                candidates.add(g)

    # Try 2: Strip first path component (module name) - handles "module_name/internal/pkg"
    parts = import_path.split("/")
    if len(parts) > 1:
        subpath = "/".join(parts[1:])  # Skip module name
        candidate = project_path / subpath
        if candidate.exists() and candidate.is_dir():
            for g in sorted(candidate.glob("*.go")):
                try:
                    candidates.add(g.relative_to(project_path))
                except ValueError:
                    candidates.add(g)
            if candidates:
                return candidates

    # Try 3: Just the last path component
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
        from ast_tools import ts_backend
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
    """Build weighted adjacency from the semantic database's symbol edges.

    Queries the indexed edges table (CALLS, IMPORTS, INHERITS, INSTANTIATES),
    maps symbols to their file paths, and aggregates edges at the module level.
    Different edge types get different weights:
        - calls:        1.0 × edge_weight
        - imports:      0.7 × edge_weight
        - inherits:     0.5 × edge_weight
        - instantiates: 0.5 × edge_weight

    Falls back to import-based adjacency if no database found.

    Args:
        project_root: Root of the project to analyze.
        database_path: Path to the semantic index database. If None, auto-detect
                      in project_root (default: project_root/.db/ast_tools.db).
        edge_weight: Base weight multiplier.

    Returns:
        Tuple of (adjacency_matrix, module_names).
    """
    import sqlite3

    # Auto-detect database path
    if database_path is None:
        candidates = [
            Path(project_root) / ".db" / "ast_tools.db",
            Path(project_root) / "ast_tools.db",
            Path(project_root) / "index" / "ast_tools.db",
        ]
        db_path: Path | None = None
        for c in candidates:
            if c.exists():
                db_path = c
                break
    else:
        db_path = Path(database_path)

    if db_path is None or not db_path.exists():
        logger.info("No semantic database found, falling back to import graph")
        return _build_module_adjacency(project_root, edge_weight=edge_weight)

    logger.info(f"Using semantic database: {db_path}")

    # Edge type → relative weight
    EDGE_WEIGHTS = {
        "calls": 1.0,
        "imports": 0.7,
        "inherits": 0.5,
        "instantiates": 0.5,
    }

    # Resolve project root for relative paths
    project_path = Path(project_root).resolve()
    adjacency: dict[tuple[str, str], float] = defaultdict(float)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Query all resolved edges with their source & target symbol info
        query = """
            SELECT e.edge_type,
                   s.file_path AS src_file,
                   t.file_path AS tgt_file,
                   s.lang AS src_lang,
                   t.lang AS tgt_lang
            FROM edges e
            JOIN symbols s ON e.source_id = s.id
            JOIN symbols t ON e.target_id = t.id
            WHERE e.resolution_state = 2
              AND s.file_path IS NOT NULL
              AND t.file_path IS NOT NULL
        """
        rows = conn.execute(query).fetchall()

        # Also get unresolved edges (target_name may map to a known file)
        query_unresolved = """
            SELECT e.edge_type, e.target_name,
                   s.file_path AS src_file,
                   s.lang AS src_lang
            FROM edges e
            JOIN symbols s ON e.source_id = s.id
            WHERE e.resolution_state != 2
              AND s.file_path IS NOT NULL
        """
        rows_unresolved = conn.execute(query_unresolved).fetchall()

        conn.close()

        # Process resolved edges
        module_pairs: dict[tuple[str, str], float] = defaultdict(float)

        for row in rows:
            src_file = row["src_file"]
            tgt_file = row["tgt_file"]
            etype = row["edge_type"]

            # Normalize file paths to module paths
            src_mod = _filepath_to_module(src_file, project_path)
            tgt_mod = _filepath_to_module(tgt_file, project_path)

            if src_mod and tgt_mod and src_mod != tgt_mod:
                weight = EDGE_WEIGHTS.get(etype, 0.5) * edge_weight
                key = (src_mod, tgt_mod)
                module_pairs[key] = max(module_pairs[key], weight)

        # Process unresolved edges — try to match target_name to file paths
        # Fall back on simple import graph for these
        for row in rows_unresolved:
            src_file = row["src_file"]
            etype = row["edge_type"]
            target_name = row["target_name"]
            src_mod = _filepath_to_module(src_file, project_path)
            if not src_mod:
                continue

            # Try matching target_name to known modules
            # (handles the case where target_name is a module path)
            if target_name and not target_name.startswith(("_", ".")):
                # Could be a module name like "ast_tools.tools.dependency"
                tgt_candidates = _name_to_modules(target_name, project_path)
                for tgt_mod in tgt_candidates:
                    if src_mod != tgt_mod:
                        weight = (EDGE_WEIGHTS.get(etype, 0.5) * edge_weight * 0.5)
                        key = (src_mod, tgt_mod)
                        module_pairs[key] = max(module_pairs[key], weight)

        # Build module set from all source files in the DB
        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        file_rows = conn2.execute("""
            SELECT DISTINCT file_path FROM symbols WHERE file_path IS NOT NULL
        """).fetchall()
        conn2.close()

        internal_modules: set[str] = set()
        for row in file_rows:
            mod = _filepath_to_module(row["file_path"], project_path)
            if mod:
                internal_modules.add(mod)

        # If DB gave us nothing useful, fall back
        if not internal_modules:
            logger.info("No modules from DB, falling back to import graph")
            return _build_module_adjacency(project_root, edge_weight=edge_weight)

        # Add edges from DB
        for (src, tgt), w in module_pairs.items():
            if src in internal_modules and tgt in internal_modules:
                adjacency[(src, tgt)] += w
                adjacency[(tgt, src)] += w

        # Also add import graph edges for coverage
        import_adj, import_names = _build_module_adjacency(
            project_root, edge_weight=edge_weight * 0.5, include_submodules=True
        )
        import_index = {name: i for i, name in enumerate(import_names)}
        for i, src_name in enumerate(import_names):
            for j in range(i + 1, len(import_names)):
                if import_adj[i, j] > 0:
                    if src_name in internal_modules and import_names[j] in internal_modules:
                        adjacency[(src_name, import_names[j])] += import_adj[i, j]
                        adjacency[(import_names[j], src_name)] += import_adj[i, j]

        # Build matrix
        module_names = sorted(internal_modules)
        n = len(module_names)
        if n == 0:
            return _build_module_adjacency(project_root, edge_weight=edge_weight)

        module_index = {m: i for i, m in enumerate(module_names)}
        adj = np.zeros((n, n), dtype=np.float64)
        for (src, tgt), w in adjacency.items():
            if src in module_index and tgt in module_index:
                i, j = module_index[src], module_index[tgt]
                adj[i, j] += w
                adj[j, i] += w

        logger.info(f"Call graph adjacency: {len(module_names)} modules, "
                    f"{len(adj.nonzero()[0]) // 2} edges")
        return adj, module_names

    except (sqlite3.Error, OSError) as e:
        logger.warning(f"Database error ({e}), falling back to import graph")
        return _build_module_adjacency(project_root, edge_weight=edge_weight)


def _filepath_to_module(file_path: str, project_path: Path) -> str | None:
    """Convert a database file_path to a canonical module name.

    Handles both absolute paths and paths relative to project root.
    """
    fp = Path(file_path)
    try:
        rel = fp.relative_to(project_path)
    except ValueError:
        # Maybe it's already relative
        try:
            rel = Path(file_path).relative_to(project_path)
        except ValueError:
            return None

    parts = list(rel.parts)
    if not parts:
        return None

    name = parts[-1]
    # Strip double extensions like .py, .ts, etc.
    if name.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".c", ".h", ".cpp", ".hpp")):
        dot = name.find(".")
        if dot > 0:
            parts[-1] = name[:dot]

    # Handle __init__ → parent dir
    if parts[-1] == "__init__":
        parts = parts[:-1]

    if not parts:
        return None

    return ".".join(parts)


def _name_to_modules(name: str, project_path: Path) -> set[str]:
    """Try to match a symbol/target name to internal module paths.

    Converts dotted names to potential filesystem paths and checks
    if they exist relative to project_root.
    """
    candidates: set[str] = set()

    # Try the dotted name as-is as a potential module
    candidates.add(name)

    # Try stripping one component at a time (e.g. pkg.mod.Class → pkg.mod)
    parts = name.split(".")
    for i in range(len(parts) - 1, 0, -1):
        candidate = ".".join(parts[:i])
        candidates.add(candidate)

    # Try as a filesystem path
    path_candidate = project_path / name.replace(".", "/")
    if path_candidate.exists() and path_candidate.is_dir():
        for f in sorted(path_candidate.rglob("*")):
            if f.suffix in _EXT_TO_LANG and f.is_file():
                try:
                    rel = f.relative_to(project_path)
                    mod = _filepath_to_module(str(rel), project_path)
                    if mod:
                        candidates.add(mod)
                except ValueError:
                    pass

    return candidates


# ── Embedding Cache (P0) ───────────────────────────────────────────────────────


class EmbeddingCache:
    """Simple LRU cache for module embeddings keyed by (file_path, content_hash, model).

    Prevents re-encoding unchanged modules on repeated suggest_modules calls.
    Thread-safe for concurrent reads (dict operations are atomic in CPython).
    """

    def __init__(self, max_entries: int = 512):
        self._cache: dict[tuple[str, str, str], list[float]] = {}
        self._order: list[tuple[str, str, str]] = []
        self._max_entries = max_entries

    def get(self, file_path: str, content_hash: str, model: str = "all-MiniLM-L6-v2") -> list[float] | None:
        """Get cached embedding. Returns None on miss.
        
        Args:
            file_path: Absolute path to the source file.
            content_hash: Hash of file content (e.g. SHA256 hex).
            model: Embedding model name.
        Returns:
            Cached embedding list or None.
        """
        key = (file_path, content_hash, model)
        val = self._cache.get(key)
        if val is not None:
            # Move to end (most recently used)
            try:
                self._order.remove(key)
                self._order.append(key)
            except ValueError:
                pass
            return val
        return None

    def put(self, file_path: str, content_hash: str, embedding: list[float], model: str = "all-MiniLM-L6-v2") -> None:
        """Store embedding in cache. Evicts LRU entry if at capacity."""
        key = (file_path, content_hash, model)
        if key in self._cache:
            # Refresh position
            try:
                self._order.remove(key)
            except ValueError:
                pass
        elif len(self._cache) >= self._max_entries:
            # Evict least recently used
            lru_key = self._order.pop(0)
            self._cache.pop(lru_key, None)
        self._cache[key] = embedding
        self._order.append(key)

    def clear(self) -> None:
        """Clear all cached embeddings."""
        self._cache.clear()
        self._order.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


# Global cache instance (shared across calls for the same process lifetime)
_EMBEDDING_CACHE = EmbeddingCache()

# ── Semantic Affinity Adjacency ──────────────────────────────────────────────


def _build_semantic_adjacency(
    project_root: str,
    module_names: list[str],
    file_to_module: dict[Path, str] | None = None,
    semantic_weight: float = 0.3,
    cache: EmbeddingCache | None = None,
) -> np.ndarray:
    """Build adjacency from semantic similarity between module documents.

    Generates text embeddings for each module's source content and adds edges
    weighted by cosine similarity. Only adds edges above 0.5 cosine similarity.
    Uses EmbeddingCache to avoid re-encoding unchanged files.

    Gracefully degrades to zero matrix if sentence-transformers is unavailable.

    Args:
        project_root: Root of the project.
        module_names: Sorted list of module names to analyze.
        file_to_module: Optional mapping of file paths to module names.
        semantic_weight: Multiplier for semantic edges (default: 0.3).
        cache: Optional embedding cache to reuse across calls.

    Returns:
        N×N symmetric adjacency matrix, or zeros if model unavailable.
    """
    n = len(module_names)
    if n == 0:
        return np.zeros((0, 0))

    project_path = Path(project_root)
    mod_to_file: dict[str, Path] = {}
    if file_to_module:
        for f, m in file_to_module.items():
            mod_to_file[m] = f
    else:
        for f in _iter_source_files(project_path):
            m = _file_to_module_name(f, project_path)
            mod_to_file[m] = f

    module_docs: list[str] = []
    content_hashes: list[str] = []
    cached_embeddings: list[list[float] | None] = [None] * n
    use_cache = cache is not None
    cached_count = 0

    for i, mod in enumerate(module_names):
        f = mod_to_file.get(mod)
        if not f:
            module_docs.append("")
            content_hashes.append("")
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")[:2000]
            module_docs.append(text)
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            content_hashes.append(h)

            # Check cache
            if use_cache:
                cached = cache.get(str(f.resolve()), h)
                if cached is not None:
                    cached_embeddings[i] = cached
                    cached_count += 1
        except OSError:
            module_docs.append("")
            content_hashes.append("")

    # If all embeddings cached, skip model loading entirely
    if use_cache and cached_count == n:
        logger.info(f"All {n} embeddings loaded from cache")
        embeddings_np = np.array([cached_embeddings[i] for i in range(n)], dtype=np.float64)
    else:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.info("sentence-transformers not installed, skipping semantic affinity")
            return np.zeros((n, n))

        try:
            model_name = "all-MiniLM-L6-v2"
            logger.info(f"Loading embedding model for semantic affinity: {model_name}")
            model = SentenceTransformer(model_name)
            logger.info(f"Generating {len(module_docs)} module embeddings...")
            embeddings_np = model.encode(module_docs, show_progress_bar=False, batch_size=32)
            logger.info("Computing cosine similarity matrix...")
        except Exception as e:
            logger.warning(f"Failed to generate semantic embeddings ({e}), skipping")
            return np.zeros((n, n))

        # Store in cache for future calls
        if use_cache:
            for i, mod in enumerate(module_names):
                f = mod_to_file.get(mod)
                if f and content_hashes[i]:
                    try:
                        cache.put(str(f.resolve()), content_hashes[i], embeddings_np[i].tolist())
                    except Exception:
                        pass

    adj = np.zeros((n, n), dtype=np.float64)
    SIMILARITY_THRESHOLD = 0.5
    for i in range(n):
        if not module_docs[i]:
            continue
        vi = embeddings_np[i]
        if isinstance(vi, (list, tuple)):
            vi = np.array(vi, dtype=np.float64)
        for j in range(i + 1, n):
            if not module_docs[j]:
                continue
            vj = embeddings_np[j]
            if isinstance(vj, (list, tuple)):
                vj = np.array(vj, dtype=np.float64)
            dot = np.dot(vi, vj)
            norm_i = np.linalg.norm(vi)
            norm_j = np.linalg.norm(vj)
            if norm_i > 1e-10 and norm_j > 1e-10:
                sim = dot / (norm_i * norm_j)
                if sim > SIMILARITY_THRESHOLD:
                    w = sim * semantic_weight
                    adj[i, j] += w
                    adj[j, i] += w

    logger.info(f"Semantic affinity: {len(adj.nonzero()[0]) // 2} edges added")
    return adj


# ── Co-Change Adjacency ──────────────────────────────────────────────────────


def _build_cochange_adjacency(
    project_root: str,
    module_names: list[str],
    cochange_weight: float = 0.4,
    max_commits: int = 1000,
) -> np.ndarray:
    """Build adjacency from git co-change frequency (evolutionary coupling).

    Analyzes git history to find modules that frequently change together.
    Uses Jaccard similarity on commit co-occurrence.

    Gracefully degrades to zero matrix if the project is not a git repo,
    git is not installed, or no commits found.

    Args:
        project_root: Root of the project (must be a git repo).
        module_names: Sorted list of module names to analyze.
        cochange_weight: Multiplier for co-change edges (default: 0.4).
        max_commits: Maximum number of recent commits (default: 1000).

    Returns:
        N×N symmetric adjacency matrix, or zeros if git unavailable.
    """
    n = len(module_names)
    if n == 0:
        return np.zeros((0, 0))

    import subprocess

    project_path = Path(project_root)
    git_dir = project_path / ".git"
    if not git_dir.exists():
        logger.info("Not a git repository, skipping co-change analysis")
        return np.zeros((n, n))

    # Map module names to relative file paths
    mod_to_relpath: dict[str, str] = {}
    relpath_to_mod: dict[str, str] = {}
    for mod in module_names:
        parts = mod.split(".")
        base_path = "/".join(parts)
        for ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".c", ".h", ".cpp", ".hpp"):
            rel = base_path + ext
            if (project_path / rel).exists():
                mod_to_relpath[mod] = rel
                relpath_to_mod[rel] = mod
                break
        else:
            # __init__.py, mod.rs, index.ts patterns
            for init in (f"{base_path}/__init__.py", f"{base_path}/mod.rs", f"{base_path}/index.ts"):
                if (project_path / init).exists():
                    mod_to_relpath[mod] = init
                    relpath_to_mod[init] = mod
                    break

    if not mod_to_relpath:
        logger.info("No module-to-file mappings, skipping co-change")
        return np.zeros((n, n))

    tracked: set[str] = set(mod_to_relpath.values())

    try:
        result = subprocess.run(
            [
                "git", "log", "--all", "--name-only",
                f"--max-count={max_commits}",
                "--diff-filter=M",
                "--pretty=format:%H",
            ],
            capture_output=True, text=True, cwd=project_root, timeout=30,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        logger.warning(f"Git co-change failed ({e}), skipping")
        return np.zeros((n, n))

    if result.returncode != 0 or not result.stdout.strip():
        logger.info("No git history, skipping co-change")
        return np.zeros((n, n))

    cochange: dict[tuple[str, str], int] = defaultdict(int)
    file_changes: dict[str, int] = defaultdict(int)
    current_files: list[str] = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            tracked_in = [f for f in current_files if f in tracked]
            for i in range(len(tracked_in)):
                file_changes[tracked_in[i]] += 1
                for j in range(i + 1, len(tracked_in)):
                    key = tuple(sorted([tracked_in[i], tracked_in[j]]))
                    cochange[key] += 1
            current_files = []
        else:
            current_files.append(line)

    tracked_in = [f for f in current_files if f in tracked]
    for i in range(len(tracked_in)):
        file_changes[tracked_in[i]] += 1
        for j in range(i + 1, len(tracked_in)):
            key = tuple(sorted([tracked_in[i], tracked_in[j]]))
            cochange[key] += 1

    if not cochange:
        logger.info("No co-change pairs, skipping")
        return np.zeros((n, n))

    adj = np.zeros((n, n), dtype=np.float64)
    MIN_JACCARD = 0.05
    for (fa, fb), both in cochange.items():
        ca = file_changes[fa]
        cb = file_changes[fb]
        union = ca + cb - both
        if union > 0:
            jac = both / union
            if jac > MIN_JACCARD:
                ma = relpath_to_mod.get(fa)
                mb = relpath_to_mod.get(fb)
                if ma and mb and ma != mb:
                    i, j = module_names.index(ma), module_names.index(mb)
                    w = jac * cochange_weight
                    adj[i, j] += w
                    adj[j, i] += w

    ec = len(adj.nonzero()[0]) // 2
    if ec > 0:
        logger.info(f"Co-change: {ec} edges from {len(cochange)} pairs")
    return adj


# ── Cluster Naming ──────────────────────────────────────────────────────────


def _derive_cluster_name(modules: list[str]) -> str:
    """Derive a descriptive name for a cluster from its module paths.

    Finds the longest common prefix of dot-delimited module paths.
    Examples:
        [ast_tools.tools.spectral, ast_tools.tools.dependency] → "ast_tools.tools"
        [ast_tools.tools, ast_tools.database]                 → "ast_tools"
        [frontend.app, frontend.components.button]             → "frontend"
        [helpers]                                              → "helpers"
        []                                                     → ""

    Args:
        modules: Sorted list of dot-delimited module paths.

    Returns:
        Common prefix as a descriptive cluster name.
    """
    if not modules:
        return ""
    if len(modules) == 1:
        return modules[0]

    # Split each module into parts
    parts_list = [m.split(".") for m in modules]

    # Find longest common prefix
    common = parts_list[0]
    for parts in parts_list[1:]:
        i = 0
        while i < len(common) and i < len(parts) and common[i] == parts[i]:
            i += 1
        common = common[:i]
        if not common:
            break

    return ".".join(common) if common else modules[0]


def _assign_cluster_names(
    clusters: list[ClusterAssignment],
) -> None:
    """Assign descriptive names to all clusters, disambiguating duplicates.

    Scans for clusters that share the same derived name and appends
    a distinguishing suffix (e.g. "tools", "tools_2", "tools_3").
    """
    name_counts: dict[str, int] = {}
    for c in clusters:
        name_counts[c.name] = name_counts.get(c.name, 0) + 1

    seen: dict[str, int] = {}
    for c in clusters:
        if name_counts[c.name] > 1:
            seen[c.name] = seen.get(c.name, 0) + 1
            if seen[c.name] > 1:
                c.name = f"{c.name}_{seen[c.name]}"
        elif c.name == "":
            # Fallback for clusters with no common prefix
            c.name = f"cluster_{c.cluster_id}"


# ── Public API ────────────────────────────────────────────────────────────────


def suggest_modules(
    project_root: str | None = None,
    min_cluster_size: int = 2,
    max_clusters: int | None = None,
    edge_weight: float = 1.0,
    database_path: str | None = None,
    use_call_graph: bool = False,
    semantic_weight: float = 0.0,
    cochange_weight: float = 0.0,
    config: SpectralConfig | None = None,
) -> SpectralResult:
    """Suggest module decomposition using spectral clustering.

    Builds a weighted dependency graph from multiple signal sources:
    - Import graph (all supported languages)
    - Database-backed call graph (optional, use_call_graph=True)
    - Semantic similarity via embeddings (optional, semantic_weight > 0)
    - Git co-change history (optional, cochange_weight > 0)

    All enabled sources are fused additively into a single adjacency matrix,
    then recursively partitioned using the Fiedler vector.

    Args:
        project_root: Root directory of the project to analyze.
            Ignored if ``config`` is provided (use ``config.project_root`` instead).
        min_cluster_size: Minimum modules per cluster (default: 2).
        max_clusters: Maximum clusters (None = auto-determined).
        edge_weight: Base weight for import/dependency edges (default: 1.0).
        database_path: Path to semantic database (for call graph).
        use_call_graph: If True, enrich with DB symbol edges (default: False).
        semantic_weight: Weight for semantic similarity edges.
            0.0 = disabled (default). Recommended: 0.2–0.5.
        cochange_weight: Weight for git co-change edges.
            0.0 = disabled (default). Recommended: 0.3–0.6.
        config: SpectralConfig instance. When provided, all other kwargs are
            ignored in favor of the config's fields. This is the recommended
            way to call ``suggest_modules`` for clarity and extensibility.

    Returns:
        SpectralResult with cluster assignments, tree, and quality metrics.
    """
    # Unpack config if provided (overrides individual kwargs)
    if config is not None:
        project_root = config.project_root
        min_cluster_size = config.min_cluster_size
        max_clusters = config.max_clusters
        edge_weight = config.edge_weight
        database_path = config.database_path
        use_call_graph = config.use_call_graph
        semantic_weight = config.semantic_weight
        cochange_weight = config.cochange_weight

    if not project_root:
        raise ValueError("project_root is required")
    project_path = Path(project_root)
    if not project_path.is_dir():
        raise ValueError(f"Project root does not exist: {project_root}")

    # Step 1: Build adjacency matrices from enabled sources
    if use_call_graph:
        adj, module_names = _build_call_graph_adjacency(project_root, database_path, edge_weight)
    else:
        adj, module_names = _build_module_adjacency(project_root, edge_weight)

    # Fuse semantic affinity edges
    if semantic_weight > 0:
        sem_adj = _build_semantic_adjacency(
            project_root, module_names, semantic_weight=semantic_weight,
            cache=_EMBEDDING_CACHE,
        )
        if sem_adj.shape == adj.shape:
            adj += sem_adj

    # Fuse co-change edges
    if cochange_weight > 0:
        co_adj = _build_cochange_adjacency(
            project_root, module_names, cochange_weight=cochange_weight,
        )
        if co_adj.shape == adj.shape:
            adj += co_adj

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
            ClusterAssignment(cluster_id=i, modules=[m], size=1, name=m)
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
    _, alg_conn = _fiedler_vector_scalable(full_laplacian, len(connected_names))

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
                name=_derive_cluster_name(mods),
                cohesion=cohesion,
                coupling=coupling,
            )
        )

    # Assign isolated modules as singleton clusters
    for i, mod in enumerate(isolated_modules):
        cid = len(clusters_out) + i
        cluster_assignments[mod] = cid
        clusters_out.append(
            ClusterAssignment(cluster_id=cid, modules=[mod], size=1, name=mod)
        )

    # Assign descriptive cluster names and disambiguate duplicates
    _assign_cluster_names(clusters_out)

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

    Builds a weighted dependency graph from the project's import structure
    (plus optional call graph, semantic similarity, and co-change), then
    recursively partitions using the Fiedler vector.

    Args (from MCP):
        project_root: Root directory of the project.
        min_cluster_size: Minimum modules per cluster (default: 2).
        max_clusters: Maximum clusters to produce (default: None = auto).
        edge_weight: Weight for dependency edges (default: 1.0).
        use_call_graph: If True, use enriched call graph (default: False).
        semantic_weight: Weight for semantic similarity (default: 0.0 = off).
        cochange_weight: Weight for git co-change (default: 0.0 = off).

    Returns:
        Dict with clusters, num_modules, num_clusters, quality, ...
    """
    config = SpectralConfig.from_dict(args)
    result = suggest_modules(config=config)

    return {
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "name": c.name,
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
