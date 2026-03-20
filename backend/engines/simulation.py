"""Simulation engine — directed graph + DFS delta propagation (F-03)."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph(
    coefficient_cache: dict[str, list[tuple[str, float]]],
) -> dict[str, list[tuple[str, float]]]:
    """Build a directed graph from the coefficient cache.

    Parameters
    ----------
    coefficient_cache : dict
        Mapping ``source_variable -> [(target_variable, coefficient), ...]``.

    Returns
    -------
    dict
        The same structure (identity transform in v1 — exists for future
        graph pre-processing).
    """
    return dict(coefficient_cache)


# ---------------------------------------------------------------------------
# DFS propagation
# ---------------------------------------------------------------------------

def dfs_propagate(
    graph: dict[str, list[tuple[str, float]]],
    start_var: str,
    delta: float,
    visited: set[str] | None = None,
) -> dict[str, float]:
    """Propagate a delta through the directed graph via DFS.

    Parameters
    ----------
    graph : dict
        Directed graph ``{ source -> [(target, coef)] }``.
    start_var : str
        The variable being changed.
    delta : float
        Fractional change (e.g. 0.20 = +20 %).
    visited : set, optional
        Nodes already visited — used to break cycles.

    Returns
    -------
    dict
        Mapping ``target_variable -> accumulated_delta_pct`` for all
        reachable nodes (excluding *start_var*).
    """
    if visited is None:
        visited = set()

    visited.add(start_var)
    impacts: dict[str, float] = {}

    neighbours = graph.get(start_var, [])
    for target, coef in neighbours:
        if target in visited:
            continue  # cycle prevention

        impact = coef * delta
        # Accumulate impact (additive across paths)
        impacts[target] = impacts.get(target, 0.0) + impact

        # Recurse for multi-hop propagation
        sub_impacts = dfs_propagate(graph, target, impact, visited.copy())
        for sub_target, sub_delta in sub_impacts.items():
            if sub_target != start_var:
                impacts[sub_target] = impacts.get(sub_target, 0.0) + sub_delta

    return impacts
