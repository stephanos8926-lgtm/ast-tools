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

from ast_tools.tools.dependency import _iter_project_python_files, build_import_graph

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


def _build_module_adjacency(
    project_root: str,
    edge_weight: float = 1.0,
    include_submodules: bool = True,
) -> tuple[np.ndarray, list[str]]:
    """Build a weighted adjacency matrix from the module-level import graph.

    Args:
        project_root: Root of the project to analyze.
        edge_weight: Weight for import edges (default: 1.0).
        include_submodules: If True, include submodule edges (e.g. a.b -> a)
                           as weaker edges (weight * 0.3).

    Returns:
        Tuple of (adjacency_matrix, module_names).
        adjacency_matrix is N×N symmetric with edge weights.
        module_names[i] is the module path corresponding to row i.
    """
    import_graph = build_import_graph(project_root)

    # Filter to only project-internal modules
    all_modules = sorted(import_graph.keys())

    if not all_modules:
        return np.zeros((0, 0)), []

    n = len(all_modules)
    module_index = {m: i for i, m in enumerate(all_modules)}
    adj = np.zeros((n, n), dtype=np.float64)

    for source, targets in import_graph.items():
        if source not in module_index:
            continue
        si = module_index[source]
        for target in targets:
            # Check if target is an internal module (has its own imports)
            if target in module_index:
                ti = module_index[target]
                adj[si, ti] += edge_weight
                adj[ti, si] += edge_weight  # Make symmetric
            elif include_submodules:
                # Try to match target as a prefix (submodule relationship)
                for internal_mod in all_modules:
                    if internal_mod.startswith(target + ".") or internal_mod == target:
                        ti = module_index[internal_mod]
                        adj[si, ti] += edge_weight * 0.3
                        adj[ti, si] += edge_weight * 0.3

    return adj, all_modules


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
