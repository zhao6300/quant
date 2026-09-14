from __future__ import annotations


def can_run_queries(seed: str) -> bool:
    return seed in {"reports", "pulls", "invalid"}
