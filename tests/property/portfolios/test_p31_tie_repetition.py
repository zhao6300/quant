from __future__ import annotations

from decimal import Decimal, localcontext

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.domain.portfolios import build_score_weighted_portfolio


def _model_oracle(scores_by_asset: dict[str, tuple[Decimal, str, int]]) -> tuple[tuple[str, Decimal], ...]:
    ordered = sorted(scores_by_asset.items())
    total = sum((score for _asset, (score, _group, _count) in ordered), Decimal(0))
    with localcontext() as context:
        context.prec = 80
        weights = [(asset_id, score / total) for asset_id, (score, _group, _count) in ordered]
    largest = max(range(len(weights)), key=lambda index: weights[index][1])
    residual = Decimal(1) - sum((weight for _asset_id, weight in weights), Decimal(0))
    asset_id, weight = weights[largest]
    weights[largest] = (asset_id, weight + residual)
    return tuple(weights)


@settings(max_examples=100, deadline=None)
@given(
    st.lists(
        st.tuples(st.sampled_from(tuple(f"asset-{rank}" for rank in range(6))), st.integers(1, 5)),
        min_size=1,
        max_size=6,
        unique_by=lambda item: item[0],
    )
)
def test_p31_score_weighting_tie_breakers_and_repeats_are_deterministic(
    scores: list[tuple[str, int]],
) -> None:
    """Property 31: score weighting repeats and ties resolve in canonical asset order."""

    scores_by_asset = {asset_id: (Decimal(score), "group", 1) for asset_id, score in scores}
    first = build_score_weighted_portfolio(scores_by_asset)
    second = build_score_weighted_portfolio(scores_by_asset)

    assert first.weights_by_asset == second.weights_by_asset
    assert first.weights_by_asset == build_score_weighted_portfolio(scores_by_asset).weights_by_asset
