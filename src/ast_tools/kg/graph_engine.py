"""Graph query engine for the ast-tools knowledge graph.

Provides graph traversal, neighborhood analysis, and centrality queries
over the existing symbols + edges + dependency_metrics tables (schema v5).
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


class GraphEngine:
    """Graph query engine over the symbols + edges tables.

    Read-only — does not create or migrate tables. Uses existing
    schema v5 tables: symbols, edges, dependency_metrics.
    """

    def __init__(self, db_path: str | Path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _symbol_details(self, symbol_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch symbol details from the symbols table.

        Returns dict[symbol_id -> {id, name, file_path, kind, line}]
        """
        if not symbol_ids:
            return {}
        placeholders = ",".join("?" for _ in symbol_ids)
        rows = self.conn.execute(
            f"SELECT id, name, file_path, kind, line FROM symbols WHERE id IN ({placeholders})",
            symbol_ids,
        ).fetchall()
        return {r["id"]: dict(r) for r in rows}

    def _all_edges(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT source_symbol_id, target_symbol_id, edge_type, weight FROM edges"
        ).fetchall()
        return [dict(r) for r in rows]

    def _outgoing_edges(self, node: str) -> list[dict[str, Any]]:
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT source_symbol_id, target_symbol_id, edge_type, weight FROM edges WHERE source_symbol_id = ?",
                (node,),
            ).fetchall()
        ]

    def _incoming_edges(self, node: str) -> list[dict[str, Any]]:
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT source_symbol_id, target_symbol_id, edge_type, weight FROM edges WHERE target_symbol_id = ?",
                (node,),
            ).fetchall()
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_neighborhood(
        self, symbol_id: str, max_depth: int = 2, max_nodes: int = 50
    ) -> dict[str, Any]:
        """Get all symbols within N hops of the starting symbol (BFS)."""
        visited: set[str] = {symbol_id}
        levels: dict[int, list[str]] = {0: [symbol_id]}
        all_nodes: set[str] = {symbol_id}
        collected_edges: list[dict[str, Any]] = []
        queue: deque[tuple[str, int]] = deque()
        queue.append((symbol_id, 0))

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in self._outgoing_edges(current):
                target = edge["target_symbol_id"]
                collected_edges.append(edge)
                if target not in visited and len(all_nodes) < max_nodes:
                    visited.add(target)
                    all_nodes.add(target)
                    if depth + 1 not in levels:
                        levels[depth + 1] = []
                    levels[depth + 1].append(target)
                    queue.append((target, depth + 1))

        details = self._symbol_details(list(all_nodes))
        return {
            "root_symbol": symbol_id,
            "symbols": [details[s] for s in all_nodes if s in details],
            "edges": collected_edges,
            "levels": dict(levels.items()),
        }

    def shortest_path(self, from_id: str, to_id: str, max_depth: int = 10) -> dict[str, Any] | None:
        """Bidirectional BFS shortest path."""
        if from_id == to_id:
            return {"path": [from_id], "distance": 0}

        front_prev: dict[str, str | None] = {from_id: None}
        back_prev: dict[str, str | None] = {to_id: None}
        front_queue: deque[str] = deque([from_id])
        back_queue: deque[str] = deque([to_id])
        visited_front: set[str] = {from_id}
        visited_back: set[str] = {to_id}

        def _neighbors(node: str) -> list[str]:
            ns: list[str] = []
            for e in self._outgoing_edges(node):
                ns.append(e["target_symbol_id"])
            for e in self._incoming_edges(node):
                ns.append(e["source_symbol_id"])
            return ns

        for _ in range(max_depth):
            # Expand front
            for _ in range(len(front_queue)):
                cur = front_queue.popleft()
                for nb in _neighbors(cur):
                    if nb not in visited_front:
                        visited_front.add(nb)
                        front_prev[nb] = cur
                        front_queue.append(nb)
                        if nb in visited_back:
                            return self._reconstruct(from_id, to_id, nb, front_prev, back_prev)
            # Expand back
            for _ in range(len(back_queue)):
                cur = back_queue.popleft()
                for nb in _neighbors(cur):
                    if nb not in visited_back:
                        visited_back.add(nb)
                        back_prev[nb] = cur
                        back_queue.append(nb)
                        if nb in visited_front:
                            return self._reconstruct(from_id, to_id, nb, front_prev, back_prev)

        return None

    def _reconstruct(
        self,
        _from_id: str,
        _to_id: str,
        meeting: str,
        front_prev: dict[str, str | None],
        back_prev: dict[str, str | None],
    ) -> dict[str, Any]:
        """Rebuild path from bidirectional BFS meeting point."""
        path: list[str] = []
        cur: str | None = meeting
        while cur is not None:
            path.append(cur)
            cur = front_prev[cur]
        path.reverse()
        cur = back_prev.get(meeting)
        while cur is not None:
            path.append(cur)
            cur = back_prev.get(cur)
        distance = len(path) - 1
        details = self._symbol_details(path)
        # Collect edges along the path
        path_edges: list[dict[str, Any]] = []
        for i in range(len(path) - 1):
            for e in self._outgoing_edges(path[i]):
                if e["target_symbol_id"] == path[i + 1]:
                    path_edges.append(e)
                    break
            else:
                for e in self._incoming_edges(path[i]):
                    if e["source_symbol_id"] == path[i + 1]:
                        path_edges.append(e)
                        break
        return {
            "path": path,
            "distance": distance,
            "symbols": [details[s] for s in path if s in details],
            "edges": path_edges,
        }

    def get_centrality_hotspots(self, top_n: int = 10) -> list[dict[str, Any]]:
        """Return top-N symbols by PageRank/centrality from dependency_metrics."""
        rows = self.conn.execute(
            """
            SELECT dm.symbol_id, dm.centrality, dm.fan_in, dm.fan_out,
                   s.name, s.file_path, s.kind
            FROM dependency_metrics dm
            JOIN symbols s ON s.id = dm.symbol_id
            WHERE dm.centrality IS NOT NULL
            ORDER BY dm.centrality DESC
            LIMIT ?
            """,
            (top_n,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_clusters(self, min_size: int = 3) -> list[dict[str, Any]]:
        """Find weakly connected components via union-find."""
        all_edges = self._all_edges()
        if not all_edges:
            return []

        # Collect all unique nodes
        nodes: set[str] = set()
        for e in all_edges:
            nodes.add(e["source_symbol_id"])
            nodes.add(e["target_symbol_id"])

        # Union-Find
        parent: dict[str, str] = {n: n for n in nodes}
        rank: dict[str, int] = dict.fromkeys(nodes, 0)

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra == rb:
                return
            if rank[ra] < rank[rb]:
                parent[ra] = rb
            elif rank[ra] > rank[rb]:
                parent[rb] = ra
            else:
                parent[rb] = ra
                rank[ra] += 1

        for e in all_edges:
            union(e["source_symbol_id"], e["target_symbol_id"])

        # Group by root
        clusters: dict[str, set[str]] = defaultdict(set)
        for n in nodes:
            clusters[find(n)].add(n)

        # Build results
        results: list[dict[str, Any]] = []
        for cid, members in enumerate(clusters.values()):
            if len(members) < min_size:
                continue
            detail_map = self._symbol_details(list(members))
            cluster_edges = [
                {
                    "source": e["source_symbol_id"],
                    "target": e["target_symbol_id"],
                    "type": e["edge_type"],
                }
                for e in all_edges
                if e["source_symbol_id"] in members and e["target_symbol_id"] in members
            ]
            results.append(
                {
                    "cluster_id": cid,
                    "size": len(members),
                    "symbols": [detail_map[s] for s in members if s in detail_map],
                    "edges": cluster_edges,
                }
            )

        return results

    def bfs(self, start_id: str, depth_limit: int = 3) -> dict[str, Any]:
        """Standard BFS returning nodes at each depth level."""
        visited: set[str] = {start_id}
        levels: dict[int, list[str]] = {0: [start_id]}
        queue: deque[tuple[str, int]] = deque([(start_id, 0)])

        while queue:
            current, depth = queue.popleft()
            if depth >= depth_limit:
                continue
            for edge in self._outgoing_edges(current):
                target = edge["target_symbol_id"]
                if target not in visited:
                    visited.add(target)
                    if depth + 1 not in levels:
                        levels[depth + 1] = []
                    levels[depth + 1].append(target)
                    queue.append((target, depth + 1))

        details = self._symbol_details(list(visited))
        collected_edges = []
        for node in list(levels.keys()):
            for sid in levels[node]:
                collected_edges.extend(self._outgoing_edges(sid))

        return {
            "levels": dict(levels),
            "symbols": [details[s] for s in visited if s in details],
            "edges": collected_edges,
        }
