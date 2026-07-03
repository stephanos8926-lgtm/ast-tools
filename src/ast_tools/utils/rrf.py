"""Reciprocal Rank Fusion (RRF) utility for multi-factor ranking.

RRF combines multiple ranked lists into a single fused ranking using
the formula: score(id) = Σ 1 / (rank_i(id) + k) for each factor i.

This is the official RRF implementation used by all ast-tools ranking.
"""

from typing import Callable

# Standard RRF constant for 6-factor fusion.
# Literature recommends k=60 for 4+ ranking dimensions to prevent
# any single factor from dominating. The old k=1.5 was appropriate
# for 2-factor fusion but amplifies noise with 6 factors.
RRF_K = 60


def rrf_fuse(
    ranked_lists: list[list[str]],
    k: int = RRF_K,
) -> dict[str, float]:
    """Fuse multiple ranked lists using Reciprocal Rank Fusion.

    Args:
        ranked_lists: List of ranked symbol ID lists, one per factor.
                      Each list should be ordered from most-to-least relevant.
                      Empty lists are skipped.
        k: RRF constant (default: 60). Higher values = more weight spread
           across lower ranks; lower values = winner-takes-all.

    Returns:
        Dict mapping symbol_id to fused score. Higher = more relevant.
    """
    fused: dict[str, float] = {}

    for factor_ranked in ranked_lists:
        if not factor_ranked:
            continue  # Graceful degradation: skip empty factors
        for rank, symbol_id in enumerate(factor_ranked):
            fused[symbol_id] = fused.get(symbol_id, 0.0) + 1.0 / (rank + 1 + k)

    return fused


def rank_symbols(
    symbol_ids: list[str],
    key_fn: Callable[[str], float],
    reverse: bool = True,
) -> list[str]:
    """Rank symbol IDs by a key function.

    Given a list of symbol IDs and a function that returns a score for each,
    returns the IDs sorted by that score (descending by default).

    Args:
        symbol_ids: List of symbol IDs to rank.
        key_fn: Function that takes a symbol_id and returns a numeric score.
                Symbols with missing data should return 0.0.
        reverse: Sort descending (True) or ascending (False).

    Returns:
        Ranked list of symbol IDs (highest/lowest score first).
    """
    scored = [(sid, key_fn(sid)) for sid in symbol_ids]
    scored.sort(key=lambda x: x[1], reverse=reverse)
    return [sid for sid, _ in scored]


def kind_rank(kind: str) -> float:
    """Map symbol kind to a priority score for ranking.

    Functions and classes are most important, then methods,
    then variables and constants. Imports are lowest priority.
    """
    priorities = {
        "function": 5.0,
        "class": 4.0,
        "method": 3.0,
        "variable": 2.0,
        "constant": 1.0,
        "import": 1.0,
    }
    return priorities.get(kind.lower(), 0.0)