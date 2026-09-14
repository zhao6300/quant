from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from mmqp.domain.factor_evaluation import ValuationEndpoint
from mmqp.kernels.evaluation import (
    average_tie_rank,
    calculate_future_return,
    evaluate_factor_turnover,
    quantile_return_groups,
)


def test_average_tie_rank_preserves_original_order() -> None:
    assert average_tie_rank([Decimal("3"), Decimal("1"), Decimal("1")]) == [
        Decimal("3"),
        Decimal("1.5"),
        Decimal("1.5"),
    ]


def test_quantile_groups_break_ties_by_asset_id() -> None:
    factor_values = {
        "B": Decimal("1"),
        "A": Decimal("1"),
        "D": Decimal("2"),
        "C": Decimal("3"),
    }
    quantiles = quantile_return_groups(factor_values, 3)
    assert quantiles == (
        ("A", 1),
        ("B", 1),
        ("D", 2),
        ("C", 3),
    )


def test_turnover_uses_union_and_absent_weights_as_zero() -> None:
    result = evaluate_factor_turnover(
        previous_weights_by_asset={"ASSET-A": Decimal("0.2"), "ASSET-B": Decimal("0.3")},
        current_weights_by_asset={"ASSET-A": Decimal("0.4"), "ASSET-D": Decimal("0.6")},
    )
    assert result == Decimal("0.55")


def test_future_return_helper_uses_strictly_later_endpoints() -> None:
    decision_at = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    valuation_endpoints = (
        ValuationEndpoint(datetime(2024, 1, 1, 9, 31, tzinfo=UTC), Decimal("100")),
        ValuationEndpoint(datetime(2024, 1, 1, 10, tzinfo=UTC), Decimal("110")),
        ValuationEndpoint(datetime(2024, 1, 1, 11, tzinfo=UTC), Decimal("121")),
    )
    results = calculate_future_return(
        factor_date=date(2024, 1, 1),
        decision_at=decision_at,
        holding_period=1,
        valuation_endpoints_by_asset={"ASSET-A": valuation_endpoints},
    )
    assert results["ASSET-A"] == Decimal("0.1")
