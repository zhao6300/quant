from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

FactorEvaluationStatus = Literal["OK", "MISSING", "UNDEFINED"]
Status = FactorEvaluationStatus
CorrelationStatus = FactorEvaluationStatus
QuantileStatus = FactorEvaluationStatus
DataOperationType = Literal["AVERAGED", "RATE_OF_CHANGE", "IUER"]
DataOperationTypeMisfit = DataOperationType

MIN_VALUE = Decimal("1e-10")
MIN_QUANTILE_COUNT = 2
MAX_QUANTILE_COUNT = 20
MAX_FUTURE_HOLDING_PERIODS = 252
CorrelationCalculator = Callable[
    [Sequence[Decimal], Sequence[Decimal]],
    FactorEvaluationStatus | Decimal,
]


def _finite_values(values: Sequence[Decimal]) -> Sequence[Decimal] | None:
    if any(not value.is_finite() for value in values):
        return None
    return values


def _optional_weight(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal(0)


def pearson_information_coefficient(
    x_values: Sequence[Decimal],
    y_values: Sequence[Decimal],
) -> FactorEvaluationStatus | Decimal:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return "UNDEFINED"
    finite_x_values = _finite_values(x_values)
    finite_y_values = _finite_values(y_values)
    if finite_x_values is None or finite_y_values is None:
        return "UNDEFINED"
    x_values = finite_x_values
    y_values = finite_y_values
    x_mean = sum(x_values, Decimal(0)) / Decimal(len(x_values))
    y_mean = sum(y_values, Decimal(0)) / Decimal(len(y_values))
    numerator = sum(
        (value - x_mean) * (other_value - y_mean)
        for value, other_value in zip(x_values, y_values, strict=True)
    )
    x_dispersion = sum((value - x_mean) ** 2 for value in x_values)
    y_dispersion = sum((value - y_mean) ** 2 for value in y_values)
    if x_dispersion == 0 or y_dispersion == 0:
        return "UNDEFINED"
    coefficient = numerator / (x_dispersion * y_dispersion) ** Decimal("0.5")
    if not coefficient.is_finite():
        return "UNDEFINED"
    return coefficient


def average_tie_rank(values: Sequence[Decimal]) -> Sequence[Decimal] | None:
    if len(values) < 2:
        return None
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks: list[Decimal | None] = [None] * len(values)
    index = 0
    while index < len(ordered):
        tied_count = 0
        while index + tied_count < len(ordered) and ordered[index + tied_count][1] == ordered[index][1]:
            tied_count += 1
        first_rank = Decimal(index + 1)
        last_rank = Decimal(index + tied_count)
        average_rank = (first_rank + last_rank) / Decimal(2)
        for tied_index in range(tied_count):
            original_index = ordered[index + tied_index][0]
            ranks[original_index] = average_rank
        index += tied_count
    if any(rank is None for rank in ranks):
        return None
    return [rank for rank in ranks if rank is not None]


def _average_tie_rank(values: Sequence[Decimal]) -> Sequence[Decimal] | None:
    return average_tie_rank(values)


def spearman_information_coefficient(
    x_values: Sequence[Decimal],
    y_values: Sequence[Decimal],
) -> FactorEvaluationStatus | Decimal:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return "UNDEFINED"
    x_ranks = average_tie_rank(x_values)
    y_ranks = average_tie_rank(y_values)
    if x_ranks is None or y_ranks is None:
        return "UNDEFINED"
    return pearson_information_coefficient(x_ranks, y_ranks)


@dataclass(frozen=True, slots=True)
class MetricPoint:
    factor_date: date
    decision_at: datetime
    status: FactorEvaluationStatus
    value: Decimal | None
    aligned_count: int = 0
    missing_count: int = 0
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QuantilePoint:
    quantile: int
    status: FactorEvaluationStatus
    value: Decimal | None
    asset_count: int = 0
    missing_count: int = 0
    details: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValuationEndpoint:
    timestamp: datetime
    value: Decimal | None = None


@dataclass(frozen=True, slots=True)
class QuantileAllocation:
    requested_count: int
    distinct_count: int
    status: FactorEvaluationStatus
    details: tuple[str, ...] = ()
    assets: tuple[tuple[str, int], ...] = ()

    def asset_by_id(self) -> dict[str, int]:
        return dict(self.assets)


@dataclass(frozen=True, slots=True)
class FutureReturnResult:
    canonical_asset_id: str
    status: FactorEvaluationStatus
    value: Decimal | None
    decision_at: datetime
    holding_period: int | None = None
    factor_date: date | None = None
    details: tuple[str, ...] = ()
    valid_endpoint_count: int = 0
    starting_value: Decimal | None = None
    ending_value: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CrossSection:
    factor_values_by_asset: Mapping[str, Decimal]
    future_returns_by_asset: Mapping[str, Decimal | None] = field(default_factory=dict)
    valuation_endpoints_by_asset: Mapping[str, Sequence[ValuationEndpoint]] = field(default_factory=dict)
    weights_by_asset: Mapping[str, Decimal | None] = field(default_factory=dict)
    factor_date: date | None = None
    decision_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class FactorEvaluationRequest:
    evaluation_id: str
    universe_version: str
    decision_at: datetime
    holding_period: int = 1
    quantile_count: int = 10
    cross_sections: tuple[CrossSection, ...] = ()
    factor_date: date | None = None


@dataclass(frozen=True, slots=True)
class FactorEvaluation:
    evaluation_id: str
    universe_version: str
    factor_dates: tuple[date, ...]
    decision_timestamps: tuple[datetime, ...]
    future_holding_periods: int
    aligned_count: int
    missing_count: int
    coverage_ratio: Decimal
    pearson_series: tuple[MetricPoint, ...]
    spearman_series: tuple[MetricPoint, ...]
    coefficient_mean: MetricPoint | None
    coefficient_sample_std: MetricPoint | None
    quantile_returns: tuple[tuple[MetricPoint, tuple[QuantilePoint, ...]], ...]
    quantile_high_low: MetricPoint | None
    rank_autocorrelation: MetricPoint
    turnover: MetricPoint
    decision_at_timestamps: tuple[datetime, ...]
    status: FactorEvaluationStatus = "OK"
    details: tuple[str, ...] = ()


def _utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _report_date(value: datetime) -> date:
    return _utc_timestamp(value).date()


def _turnover_value(
    value_by_asset_t: Mapping[str, Decimal],
    value_by_asset_t1: Mapping[str, Decimal],
) -> Decimal:
    zero = Decimal(0)
    asset_ids = sorted(set(value_by_asset_t) | set(value_by_asset_t1))
    total = Decimal(0)
    for asset_id in asset_ids:
        previous_weight = value_by_asset_t1.get(asset_id, zero)
        current_weight = value_by_asset_t.get(asset_id, zero)
        if not current_weight.is_finite() or not previous_weight.is_finite():
            raise ValueError("weights must be finite")
        total += abs(current_weight - previous_weight)
    return total / Decimal(2)


def evaluate_factor_turnover(
    value_by_asset_t: Mapping[str, Decimal],
    value_by_asset_t1: Mapping[str, Decimal],
    factor_date_t1: date | None = None,
    decision_at_t1: datetime | None = None,
) -> Decimal | MetricPoint:
    turnover = _turnover_value(value_by_asset_t, value_by_asset_t1)
    if decision_at_t1 is None:
        return turnover
    return _metric_point(
        factor_date_t1,
        decision_at_t1,
        "OK",
        turnover,
        aligned_count=len(set(value_by_asset_t) | set(value_by_asset_t1)),
        missing_count=0,
    )


def assign_quantiles(
    quantile_count: int,
    factor_values_by_asset: Mapping[str, Decimal],
) -> QuantileAllocation:
    valid_factor_values = {
        asset_id: value for asset_id, value in factor_values_by_asset.items() if value.is_finite()
    }
    distinct_count = len(set(valid_factor_values.values()))
    if not MIN_QUANTILE_COUNT <= quantile_count <= MAX_QUANTILE_COUNT:
        return QuantileAllocation(
            quantile_count,
            distinct_count,
            "UNDEFINED",
            details=("quantile-count-out-of-range",),
        )
    if distinct_count < quantile_count:
        return QuantileAllocation(
            quantile_count,
            distinct_count,
            "UNDEFINED",
            details=("quantile-count-exceeds-distinct-factor-values",),
        )
    count = len(valid_factor_values)
    ordered_assets = sorted((value, asset_id) for asset_id, value in valid_factor_values.items())
    assets = []
    for rank, (_, asset_id) in enumerate(ordered_assets, start=1):
        group = (rank - 1) * quantile_count // count + 1
        assets.append((asset_id, min(quantile_count, group)))
    return QuantileAllocation(
        quantile_count,
        distinct_count,
        "OK",
        assets=tuple(assets),
    )


def quantile_returns(
    future_returns_by_asset: Mapping[str, Decimal | None],
    quantile_count: int,
    factor_values_by_asset: Mapping[str, Decimal],
    weights_by_asset: Mapping[str, Decimal | None] | None = None,
) -> tuple[QuantilePoint, ...]:
    allocation = assign_quantiles(quantile_count, factor_values_by_asset)
    group_count = MAX_QUANTILE_COUNT if allocation.status != "OK" else quantile_count
    groups: list[list[str]] = [[] for _ in range(group_count)]
    if allocation.status == "OK":
        for asset_id, quantile in allocation.assets:
            groups[quantile - 1].append(asset_id)
    zero_weight = Decimal(0)
    invalid_assets_by_group: list[list[str]] = [[] for _ in range(group_count)]
    points: list[QuantilePoint] = []
    for quantile, assets in enumerate(groups, start=1):
        total_weight = Decimal(0)
        weighted_sum = Decimal(0)
        for asset_id in sorted(assets):
            weight = (
                weights_by_asset.get(asset_id, Decimal(1)) if weights_by_asset is not None else Decimal(1)
            )
            if weight is None or not weight.is_finite() or weight < zero_weight:
                invalid_assets_by_group[quantile - 1].append(f"{asset_id}:invalid-weight")
                continue
            if weight == zero_weight:
                invalid_assets_by_group[quantile - 1].append(f"{asset_id}:invalid-weight")
                continue
            future_return = future_returns_by_asset.get(asset_id)
            if future_return is None or not future_return.is_finite():
                invalid_assets_by_group[quantile - 1].append(f"{asset_id}:missing-future-return")
                continue
            total_weight += weight
            weighted_sum += weight * future_return
        if allocation.status != "OK":
            points.append(
                QuantilePoint(
                    quantile=quantile,
                    status="UNDEFINED",
                    value=None,
                    details=allocation.details,
                )
            )
            continue
        if total_weight <= 0:
            details = tuple(invalid_assets_by_group[quantile - 1]) or ("total-weight-not-positive",)
            points.append(
                QuantilePoint(
                    quantile=quantile,
                    status="UNDEFINED",
                    value=None,
                    asset_count=len(assets),
                    missing_count=len(invalid_assets_by_group[quantile - 1]),
                    details=details,
                )
            )
            continue
        points.append(
            QuantilePoint(
                quantile=quantile,
                status="OK",
                value=weighted_sum / total_weight,
                asset_count=len(assets),
                missing_count=len(invalid_assets_by_group[quantile - 1]),
                details=tuple(invalid_assets_by_group[quantile - 1]),
            )
        )
    return tuple(points)


def quantile_high_low_from_group_points(
    group_points: Sequence[QuantilePoint],
) -> Decimal | None:
    values = [point.value for point in group_points if point.status == "OK" and point.value is not None]
    if not values:
        return None
    return max(values) - min(values)


@dataclass(frozen=True, slots=True)
class _RankedCrossSection:
    factor_date: date
    decision_at: datetime
    factor_values_by_asset: Mapping[str, Decimal]
    future_returns_by_asset: Mapping[str, Decimal | None]
    valuation_endpoints_by_asset: Mapping[str, Sequence[ValuationEndpoint]]
    weights_by_asset: Mapping[str, Decimal | None]


def _metric_point(
    factor_date: date | None,
    decision_at: datetime | None,
    status: FactorEvaluationStatus,
    value: Decimal | None,
    *,
    aligned_count: int = 0,
    missing_count: int = 0,
    details: tuple[str, ...] = (),
) -> MetricPoint:
    report_date = factor_date or date(1970, 1, 1)
    report_decision_at = decision_at or datetime(1970, 1, 1, tzinfo=UTC)
    return MetricPoint(
        factor_date=report_date,
        decision_at=report_decision_at,
        status=status,
        value=value,
        aligned_count=aligned_count,
        missing_count=missing_count,
        details=details,
    )


def calculate_future_returns(
    factor_date: date,
    decision_at: datetime,
    holding_period: int,
    valuation_endpoints_by_asset: Mapping[str, Sequence[ValuationEndpoint]],
) -> tuple[FutureReturnResult, ...]:
    if not 1 <= holding_period <= MAX_FUTURE_HOLDING_PERIODS:
        return tuple(
            FutureReturnResult(
                canonical_asset_id=asset_id,
                status="UNDEFINED",
                value=None,
                decision_at=decision_at,
                holding_period=holding_period,
                factor_date=factor_date,
                details=("holding-period-out-of-range",),
            )
            for asset_id in sorted(valuation_endpoints_by_asset)
        )
    required_value = holding_period + 1
    results: list[FutureReturnResult] = []
    for asset_id in sorted(valuation_endpoints_by_asset):
        invalid_details: list[str] = []
        endpoints = valuation_endpoints_by_asset.get(asset_id, ())
        valid_endpoints: list[ValuationEndpoint] = []
        for endpoint in endpoints:
            if endpoint.timestamp <= decision_at:
                invalid_details.append(f"{_utc_timestamp(endpoint.timestamp).isoformat()}:before-decision")
                continue
            if endpoint.value is None or not endpoint.value.is_finite() or endpoint.value <= 0:
                invalid_details.append(f"{_utc_timestamp(endpoint.timestamp).isoformat()}:invalid-value")
                continue
            valid_endpoints.append(endpoint)
        if len(valid_endpoints) < required_value:
            invalid_details.append("insufficient-post-decision-endpoints")
            results.append(
                FutureReturnResult(
                    canonical_asset_id=asset_id,
                    status="UNDEFINED",
                    value=None,
                    decision_at=decision_at,
                    holding_period=holding_period,
                    factor_date=factor_date,
                    valid_endpoint_count=len(valid_endpoints),
                    details=tuple(invalid_details),
                )
            )
            continue
        selected_endpoints = sorted(valid_endpoints, key=lambda endpoint: endpoint.timestamp)[:required_value]
        starting_value = selected_endpoints[0].value
        ending_value = selected_endpoints[-1].value
        if starting_value is None or ending_value is None or starting_value <= 0 or ending_value <= 0:
            invalid_details.append("invalid-selected-endpoints")
            results.append(
                FutureReturnResult(
                    canonical_asset_id=asset_id,
                    status="UNDEFINED",
                    value=None,
                    decision_at=decision_at,
                    holding_period=holding_period,
                    factor_date=factor_date,
                    details=tuple(invalid_details),
                )
            )
            continue
        results.append(
            FutureReturnResult(
                canonical_asset_id=asset_id,
                status="OK",
                value=ending_value / starting_value - Decimal(1),
                decision_at=decision_at,
                holding_period=holding_period,
                factor_date=factor_date,
                valid_endpoint_count=required_value,
                starting_value=starting_value,
                ending_value=ending_value,
            )
        )
    return tuple(results)


def _correlation_point(
    cross_section: _RankedCrossSection,
    calculator: CorrelationCalculator,
) -> MetricPoint:
    factor_values: list[Decimal] = []
    future_returns: list[Decimal | None] = []
    for asset_id in sorted(cross_section.factor_values_by_asset):
        factor_value = cross_section.factor_values_by_asset[asset_id]
        factor_values.append(factor_value)
        future_returns.append(cross_section.future_returns_by_asset.get(asset_id))
    pairs = [
        (factor_value, future_return)
        for factor_value, future_return in zip(factor_values, future_returns, strict=True)
        if future_return is not None
    ]
    invalid_factor_count = sum(1 for factor_value, _ in pairs if not factor_value.is_finite())
    invalid_return_count = sum(1 for _, future_return in pairs if not future_return.is_finite())
    result = calculator(
        [factor_value for factor_value, _ in pairs],
        [future_return for _, future_return in pairs if future_return is not None],
    )
    status = result if isinstance(result, str) else "OK"
    details: list[str] = []
    if invalid_factor_count:
        details.append("missing-factors")
    if invalid_return_count:
        details.append("missing-future-returns")
    if len(pairs) < 2:
        details.append("aligned-count-less-than-two")
    return _metric_point(
        cross_section.factor_date,
        cross_section.decision_at,
        status,
        result if isinstance(result, Decimal) else None,
        aligned_count=len(pairs),
        missing_count=invalid_factor_count + invalid_return_count,
        details=tuple(details),
    )


def _rank_cross_section(
    cross_section: CrossSection,
    global_decision_at: datetime,
    future_returns_by_asset: Mapping[str, Decimal | None] | None = None,
) -> _RankedCrossSection:
    decision_at = cross_section.decision_at or global_decision_at
    factor_date = cross_section.factor_date or _report_date(decision_at)
    normalized_future_returns = (
        dict(future_returns_by_asset)
        if future_returns_by_asset is not None
        else dict(cross_section.future_returns_by_asset)
    )
    return _RankedCrossSection(
        factor_date=factor_date,
        decision_at=_utc_timestamp(decision_at),
        factor_values_by_asset=cross_section.factor_values_by_asset,
        future_returns_by_asset=normalized_future_returns,
        valuation_endpoints_by_asset=cross_section.valuation_endpoints_by_asset,
        weights_by_asset=cross_section.weights_by_asset,
    )


def evaluate_factor(trials: Sequence[FactorEvaluationRequest]) -> tuple[FactorEvaluation, ...]:
    return tuple(evaluate_factor_request(trial) for trial in trials)


def evaluate_factor_request(
    request: FactorEvaluationRequest,
) -> FactorEvaluation:
    holding_period = request.holding_period
    if not 1 <= holding_period <= MAX_FUTURE_HOLDING_PERIODS:
        return _invalid_request(request, ("future-period-out-of-range",))
    normalized_sections: list[_RankedCrossSection] = []
    for section in request.cross_sections:
        if section.valuation_endpoints_by_asset:
            future_returns = calculate_future_returns(
                section.factor_date or _report_date(section.decision_at or request.decision_at),
                section.decision_at or request.decision_at,
                holding_period,
                section.valuation_endpoints_by_asset,
            )
            results_by_asset: dict[str, Decimal | None] = {}
            for result in future_returns:
                results_by_asset[result.canonical_asset_id] = result.value if result.status == "OK" else None
            future_returns_by_asset: Mapping[str, Decimal | None] = results_by_asset
        else:
            future_returns_by_asset = section.future_returns_by_asset
        normalized_sections.append(_rank_cross_section(section, request.decision_at, future_returns_by_asset))
    pearson_series: list[MetricPoint] = []
    spearman_series: list[MetricPoint] = []
    quantile_series: list[tuple[MetricPoint, tuple[QuantilePoint, ...]]] = []
    aligned_count = 0
    missing_count = 0
    asset_count = 0
    for cross_section in normalized_sections:
        pearson_point = _correlation_point(
            cross_section,
            pearson_information_coefficient,
        )
        spearman_point = _correlation_point(
            cross_section,
            spearman_information_coefficient,
        )
        pearson_series.append(pearson_point)
        spearman_series.append(spearman_point)
        aligned_count += pearson_point.aligned_count
        missing_count += pearson_point.missing_count
        asset_count += len(cross_section.factor_values_by_asset)
        groups = quantile_returns(
            cross_section.future_returns_by_asset,
            request.quantile_count,
            cross_section.factor_values_by_asset,
            cross_section.weights_by_asset,
        )
        quantile_point = _metric_point(
            cross_section.factor_date,
            cross_section.decision_at,
            "OK" if all(group.status == "OK" for group in groups) else "UNDEFINED",
            quantile_high_low_from_group_points(groups),
            aligned_count=sum(group.asset_count for group in groups),
            missing_count=sum(group.missing_count for group in groups),
        )
        quantile_series.append((quantile_point, groups))
    pearson_values = [point.value for point in pearson_series if point.value is not None]
    coefficient_mean = None
    coefficient_sample_std = None
    if pearson_values:
        mean = sum(pearson_values, Decimal(0)) / Decimal(len(pearson_values))
        coefficient_mean = _metric_point(
            normalized_sections[0].factor_date,
            normalized_sections[0].decision_at,
            "OK",
            mean,
            aligned_count=len(pearson_values),
        )
        if len(pearson_values) >= 2:
            sample_variance = sum((value - mean) ** 2 for value in pearson_values) / Decimal(
                len(pearson_values) - 1
            )
            coefficient_sample_std = _metric_point(
                normalized_sections[0].factor_date,
                normalized_sections[0].decision_at,
                "OK",
                sample_variance ** Decimal("0.5"),
                aligned_count=len(pearson_values),
            )
        else:
            coefficient_sample_std = _metric_point(
                normalized_sections[0].factor_date,
                normalized_sections[0].decision_at,
                "UNDEFINED",
                None,
                aligned_count=1,
            )
    rank_autocorrelation = _metric_point(
        normalized_sections[-1].factor_date,
        normalized_sections[-1].decision_at,
        "UNDEFINED",
        None,
        details=("insufficient-consecutive-sections",),
    )
    turnover = _metric_point(
        normalized_sections[-1].factor_date,
        normalized_sections[-1].decision_at,
        "UNDEFINED",
        None,
        details=("insufficient-consecutive-sections",),
    )
    if len(normalized_sections) >= 2:
        previous = normalized_sections[0]
        current = normalized_sections[-1]
        shared_assets = sorted(set(previous.factor_values_by_asset) & set(current.factor_values_by_asset))
        previous_values = [previous.factor_values_by_asset.get(asset_id) for asset_id in shared_assets]
        current_values = [current.factor_values_by_asset.get(asset_id) for asset_id in shared_assets]
        rank_autocorrelation = _rank_autocorrelation_point(
            current,
            shared_assets,
            previous_values,
            current_values,
        )
        previous_weights: dict[str, Decimal] = {
            asset_id: _optional_weight(request.cross_sections[-2].weights_by_asset.get(asset_id, Decimal(0)))
            for asset_id in shared_assets
        }
        current_weights: dict[str, Decimal] = {
            asset_id: _optional_weight(request.cross_sections[-1].weights_by_asset.get(asset_id, Decimal(0)))
            for asset_id in shared_assets
        }
        turnover = _metric_point(
            current.factor_date,
            current.decision_at,
            "OK",
            _turnover_value(previous_weights, current_weights),
            aligned_count=len(shared_assets),
        )
    request_status: FactorEvaluationStatus = "OK"
    if not normalized_sections:
        request_status = "UNDEFINED"
    coverage_ratio = Decimal(0) if asset_count == 0 else Decimal(aligned_count) / Decimal(asset_count)
    quantile_high_low = quantile_series[-1][0] if quantile_series else None
    return FactorEvaluation(
        evaluation_id=request.evaluation_id,
        universe_version=request.universe_version,
        factor_dates=tuple(section.factor_date for section in normalized_sections),
        decision_timestamps=tuple(section.decision_at for section in normalized_sections),
        future_holding_periods=holding_period,
        aligned_count=aligned_count,
        missing_count=missing_count,
        coverage_ratio=coverage_ratio,
        pearson_series=tuple(pearson_series),
        spearman_series=tuple(spearman_series),
        coefficient_mean=coefficient_mean,
        coefficient_sample_std=coefficient_sample_std,
        quantile_returns=tuple(quantile_series),
        quantile_high_low=quantile_high_low,
        rank_autocorrelation=rank_autocorrelation,
        turnover=turnover,
        decision_at_timestamps=tuple(section.decision_at for section in normalized_sections),
        status=request_status,
    )


def _rank_autocorrelation_point(
    current: _RankedCrossSection,
    shared_assets: Sequence[str],
    previous_values: list[Decimal | None],
    current_values: list[Decimal | None],
) -> MetricPoint:
    valid_pairs = [
        (previous, current)
        for previous, current in zip(previous_values, current_values, strict=True)
        if previous is not None and current is not None
    ]
    previous_ranks = average_tie_rank([previous for previous, _ in valid_pairs if previous is not None])
    current_ranks = average_tie_rank([current for _, current in valid_pairs if current is not None])
    if previous_ranks is None or current_ranks is None:
        return _metric_point(
            current.factor_date,
            current.decision_at,
            "UNDEFINED",
            None,
            aligned_count=len(valid_pairs),
            missing_count=len(shared_assets) - len(valid_pairs),
            details=("unable-to-rank-shared-values",),
        )
    result = pearson_information_coefficient(previous_ranks, current_ranks)
    return _metric_point(
        current.factor_date,
        current.decision_at,
        "OK" if isinstance(result, Decimal) else result,
        result if isinstance(result, Decimal) else None,
        aligned_count=len(valid_pairs),
    )


def _invalid_request(
    request: FactorEvaluationRequest,
    details: tuple[str, ...],
) -> FactorEvaluation:
    return FactorEvaluation(
        evaluation_id=request.evaluation_id,
        universe_version=request.universe_version,
        factor_dates=(),
        decision_timestamps=(),
        future_holding_periods=request.holding_period,
        aligned_count=0,
        missing_count=0,
        coverage_ratio=Decimal(0),
        pearson_series=(),
        spearman_series=(),
        coefficient_mean=None,
        coefficient_sample_std=None,
        quantile_returns=(),
        quantile_high_low=None,
        rank_autocorrelation=_metric_point(None, None, "UNDEFINED", None, details=details),
        turnover=_metric_point(None, None, "UNDEFINED", None, details=details),
        decision_at_timestamps=(),
        status="UNDEFINED",
        details=details,
    )
