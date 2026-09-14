from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from mmqp.domain.factor_evaluation import (
    CrossSection,
    ValuationEndpoint,
    calculate_future_returns,
    quantile_returns,
)

DECISION_AT = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)


def test_quantile_returns_helper_and_weighted_mean() -> None:
    cross_section = CrossSection(
        factor_values_by_asset={
            "ASSET-A": Decimal("1"),
            "ASSET-B": Decimal("2"),
        },
        future_returns_by_asset={
            "ASSET-A": Decimal("0.1"),
            "ASSET-B": Decimal("0.2"),
        },
        weights_by_asset={
            "ASSET-A": Decimal("0.5"),
            "ASSET-B": Decimal("0.5"),
        },
        factor_date=date(2024, 1, 1),
        decision_at=DECISION_AT,
    )
    result = calculate_future_returns(
        factor_date=cross_section.factor_date or date(1970, 1, 1),
        decision_at=cross_section.decision_at or DECISION_AT,
        holding_period=1,
        valuation_endpoints_by_asset={
            "ASSET-A": (
                ValuationEndpoint(datetime(2024, 1, 1, 9, 31, tzinfo=UTC), Decimal("100")),
                ValuationEndpoint(datetime(2024, 1, 1, 10, tzinfo=UTC), Decimal("120")),
            ),
            "ASSET-B": (
                ValuationEndpoint(datetime(2024, 1, 1, 9, 31, tzinfo=UTC), Decimal("100")),
                ValuationEndpoint(datetime(2024, 1, 1, 10, tzinfo=UTC), Decimal("200")),
            ),
        },
    )
    result_by_asset = [result.canonical_asset_id for result in result]
    assert result_by_asset == ["ASSET-A", "ASSET-B"]
    assert [result.value for result in result] == [Decimal("0.2"), Decimal("1")]
    grouped = quantile_returns(
        future_returns_by_asset={
            asset_id: result.value
            for asset_id, result in zip(cross_section.future_returns_by_asset, result, strict=True)
        },
        quantile_count=2,
        factor_values_by_asset=cross_section.factor_values_by_asset,
        weights_by_asset=cross_section.weights_by_asset,
    )
    assert [(point.quantile, point.value) for point in grouped] == [
        (1, Decimal("0.2")),
        (2, Decimal("1")),
    ]
