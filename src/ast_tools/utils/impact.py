#!/usr/bin/env python3
"""Impact analysis and dependency graph utilities."""



def build_reverse_deps(dep_graph: dict[str, list[str]]) -> dict[str, list[str]]:
    """Build reverse dependency graph (who imports FROM each module)."""
    reverse: dict[str, list[str]] = {}
    for module, deps in dep_graph.items():
        if module not in reverse:
            reverse[module] = []
        for dep in deps:
            if dep not in reverse:
                reverse[dep] = []
            reverse[dep].append(module)
    return reverse


def get_transitive_deps(
    module: str,
    dep_graph: dict[str, list[str]],
    visited: set[str] | None = None,
) -> set[str]:
    """Get all transitive dependencies of a module (what it imports, recursively)."""
    if visited is None:
        visited = set()
    if module in visited:
        return set()
    visited.add(module)
    direct = set(dep_graph.get(module, []))
    transitive = set()
    for dep in direct:
        transitive.update(get_transitive_deps(dep, dep_graph, visited))
    return direct | transitive


def classify_risk(fan_out: int) -> str:
    """Classify risk based on number of direct dependents.
    
    Thresholds matching original implementation:
    - >= 10: high
    - >= 3: medium
    - < 3: low
    """
    if fan_out >= 10:
        return "high"
    if fan_out >= 3:
        return "medium"
    return "low"