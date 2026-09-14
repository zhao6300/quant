from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mmqp.domain.factor_evaluation import QuantilePoint, assign_quantiles, quantile_returns

# Feature: multi-market-quant-platform, Property 28: Quantile allocation and return are deterministic.
ASSET_IDS = ("A", "B", "C", "D")
QUANTILE_COUNTS = (1, 2, 3, 4, 5, 20, 21)
MIN_VALID_QUANTILE_COUNT = 2
TOO_LARGE_QUANTILE_COUNT = 20
MAX_EXPECTED_QUANTILE_COUNT = 21


def _quantile_group_for_rank(rank: int, quantile_count: int, count: int) -> int:
    return min(quantile_count, (rank - 1) * quantile_count // count + 1)


def _expected_groups(
    factor_values_by_asset: Mapping[str, Decimal], quantile_count: int
) -> tuple[tuple[str, int], ...]:
    ordered_assets = sorted(
        (factor_value, asset_id) for asset_id, factor_value in factor_values_by_asset.items()
    )
    count = len(ordered_assets)
    return tuple(
        (asset_id, _quantile_group_for_rank(rank, quantile_count, count))
        for rank, (_, asset_id) in enumerate(ordered_assets, start=1)
    )


def _expected_group_points(
    future_returns_by_asset: Mapping[str, Decimal | None],
    weights_by_asset: Mapping[str, Decimal | None],
    groups: tuple[tuple[str, int], ...],
    quantile_count: int,
) -> tuple[QuantilePoint, ...]:
    grouped_assets: dict[int, list[str]] = {quantile: [] for quantile in range(1, quantile_count + 1)}
    for asset_id, quantile in groups:
        grouped_assets[quantile].append(asset_id)

    points: list[QuantilePoint] = []
    for quantile, asset_ids in grouped_assets.items():
        weighted_sum = Decimal(0)
        total_weight = Decimal(0)
        missing_count = 0
        details: list[str] = []
        for asset_id in sorted(asset_ids):
            weight = weights_by_asset.get(asset_id) if weights_by_asset else Decimal(1)
            future_return = future_returns_by_asset.get(asset_id)
            if weight is None or not weight.is_finite() or weight <= Decimal(0):
                missing_count += 1
                details.append(f"{asset_id}:invalid-weight")
                continue
            if future_return is None or not future_return.is_finite():
                missing_count += 1
                details.append(f"{asset_id}:missing-future-return")
                continue
            total_weight += weight
            weighted_sum += weight * future_return
        points.append(
            QuantilePoint(
                quantile=quantile,
                status="OK" if total_weight > Decimal(0) else "UNDEFINED",
                value=weighted_sum / total_weight if total_weight > Decimal(0) else None,
                asset_count=len(asset_ids),
                missing_count=missing_count,
                details=tuple(details)
                if missing_count
                else ("total-weight-not-positive",)
                if total_weight <= Decimal(0)
                else (),
            )
        )
    return tuple(points)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=(HealthCheck.too_slow,),
)
@given(
    factor_values_by_asset=st.fixed_dictionaries(
        {asset_id: st.decimals(allow_nan=False, allow_infinity=False) for asset_id in ASSET_IDS}
    ),
    future_returns_by_asset=st.fixed_dictionaries(
        {
            asset_id: st.one_of(
                st.none(),
                st.decimals(allow_nan=False, allow_infinity=False),
            )
            for asset_id in ASSET_IDS
        }
    ),
    weights_by_asset=st.fixed_dictionaries(
        {
            asset_id: st.one_of(
                st.none(),
                st.decimals(allow_nan=False, allow_infinity=False),
            )
            for asset_id in ASSET_IDS
        }
    ),
    quantile_count=st.sampled_from(QUANTILE_COUNTS),
)
def test_quantile_allocation_and_returns_are_deterministic(
    factor_values_by_asset: Mapping[str, Decimal],
    future_returns_by_asset: Mapping[str, Decimal | None],
    weights_by_asset: Mapping[str, Decimal | None],
    quantile_count: int,
) -> None:
    actual = assign_quantiles(quantile_count, factor_values_by_asset)
    distinct_count = len(set(factor_values_by_asset.values()))
    out_of_range = quantile_count < MIN_VALID_QUANTILE_COUNT or quantile_count > TOO_LARGE_QUANTILE_COUNT
    if out_of_range:
        assert actual.status == "UNDEFINED"
        assert actual.details == ("quantile-count-out-of-range",)
    elif distinct_count < quantile_count:
        assert actual.status == "UNDEFINED"
        assert actual.details == ("quantile-count-exceeds-distinct-factor-values",)
    else:
        assert actual.status == "OK"
        assert actual.details == ()
        assert actual.assets == _expected_groups(factor_values_by_asset, quantile_count)
    assert actual.distinct_count == distinct_count
    assert actual.requested_count == max(quantile_count, 0)

    points = quantile_returns(
        future_returns_by_asset=future_returns_by_asset,
        quantile_count=quantile_count,
        factor_values_by_asset=factor_values_by_asset,
        weights_by_asset=weights_by_asset,
    )
    if actual.status != "OK":
        return

    expected_points = _expected_group_points(
        future_returns_by_asset,
        weights_by_asset,
        groups=actual.assets,
        quantile_count=quantile_count,
    )
    assert points == expected_points

    for first_index in range(quantile_count):
        for second_index in range(first_index + 1, quantile_count):
            assert points[first_index].quantile == first_index + 1
            assert points[second_index].quantile == second_index + 1
