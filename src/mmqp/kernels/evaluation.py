from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal

from mmqp.domain.factor_evaluation import (
    FactorEvaluationStatus,
    ValuationEndpoint,
    calculate_future_returns,
)
from mmqp.domain.factor_evaluation import average_tie_rank as average_tie_rank_contract
from mmqp.domain.factor_evaluation import (
    evaluate_factor_turnover as domain_evaluate_factor_turnover,
)
from mmqp.domain.factor_evaluation import (
    pearson_information_coefficient as pearson_information_coefficient_contract,
)
from mmqp.domain.factor_evaluation import (
    spearman_information_coefficient as spearman_information_coefficient_contract,
)


def calculate_future_return(
    factor_date: date,
    decision_at: datetime,
    holding_period: int,
    valuation_endpoints_by_asset: Mapping[str, Sequence[ValuationEndpoint]],
) -> Mapping[str, Decimal | None]:
    results = calculate_future_returns(
        factor_date,
        decision_at,
        holding_period,
        valuation_endpoints_by_asset,
    )
    return {result.canonical_asset_id: result.value if result.status == "OK" else None for result in results}


def evaluate_factor_turnover(
    previous_weights_by_asset: Mapping[str, Decimal],
    current_weights_by_asset: Mapping[str, Decimal],
) -> Decimal:
    turnover = domain_evaluate_factor_turnover(current_weights_by_asset, previous_weights_by_asset)
    if isinstance(turnover, Decimal):
        return turnover
    return abs(turnover.value if turnover.value is not None else Decimal(0))


def average_tie_rank(
    values: Sequence[Decimal],
) -> Sequence[Decimal] | None:
    return average_tie_rank_contract(values)


def quantile_return_groups(
    factor_values_by_asset: Mapping[str, Decimal],
    quantile_count: int,
) -> tuple[tuple[str, int], ...]:
    ordered_assets = sorted((value, asset_id) for asset_id, value in factor_values_by_asset.items())
    count = len(ordered_assets)
    return tuple(
        (asset_id, min(quantile_count, (rank - 1) * quantile_count // count + 1))
        for rank, (_, asset_id) in enumerate(ordered_assets, start=1)
    )


def pearson_information_coefficient(
    factor_values: Sequence[Decimal],
    future_returns: Sequence[Decimal],
) -> FactorEvaluationStatus | Decimal:
    return pearson_information_coefficient_contract(factor_values, future_returns)


def spearman_information_coefficient(
    factor_values: Sequence[Decimal],
    future_returns: Sequence[Decimal],
) -> FactorEvaluationStatus | Decimal:
    return spearman_information_coefficient_contract(factor_values, future_returns)
