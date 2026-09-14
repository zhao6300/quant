from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from mmqp.domain.factor_evaluation import (
    CorrelationStatus,
    CrossSection,
    FactorEvaluation,
    FactorEvaluationRequest,
    MetricPoint,
    QuantilePoint,
    calculate_future_returns,
    pearson_information_coefficient,
    quantile_returns,
    spearman_information_coefficient,
)
from mmqp.domain.factor_evaluation import average_tie_rank as domain_average_tie_rank
from mmqp.domain.factor_evaluation import (
    evaluate_factor_request as domain_evaluate_factor_request,
)

FactorEvaluationResult = FactorEvaluation


@dataclass(frozen=True, slots=True)
class FactorSample:
    evaluation_id: str
    universe_version: str
    factor_date: date
    decision_at: datetime
    cross_section: CrossSection


@dataclass(frozen=True, slots=True)
class FutureResultMetrics:
    holding_period: int | None = None
    valid_endpoint_count: int = 0
    starting_value: Decimal | None = None
    ending_value: Decimal | None = None


class FactorEvaluationService:
    def evaluate(self, request: FactorEvaluationRequest) -> FactorEvaluationResult:
        return domain_evaluate_factor_request(request)

    def pearson_information_coefficient(
        self,
        factor_values_by_asset: Mapping[str, Decimal],
        future_returns_by_asset: Mapping[str, Decimal | None],
        factor_date: date,
        decision_at: datetime,
    ) -> MetricPoint:
        factor_values, future_returns = _aligned_values(factor_values_by_asset, future_returns_by_asset)
        result = pearson_information_coefficient(factor_values, future_returns)
        return _correlation_point(
            factor_date,
            decision_at,
            result,
            len(factor_values),
            "pearson-information-coefficient",
        )

    def spearman_information_coefficient(
        self,
        factor_values_by_asset: Mapping[str, Decimal],
        future_returns_by_asset: Mapping[str, Decimal | None],
        factor_date: date,
        decision_at: datetime,
    ) -> MetricPoint:
        factor_values, future_returns = _aligned_values(factor_values_by_asset, future_returns_by_asset)
        result = spearman_information_coefficient(factor_values, future_returns)
        return _correlation_point(
            factor_date,
            decision_at,
            result,
            len(factor_values),
            "spearman-information-coefficient",
        )

    def quantile_returns(
        self,
        cross_section: CrossSection,
        quantile_count: int,
        factor_date: date,
        decision_at: datetime,
    ) -> tuple[QuantilePoint, ...]:
        del factor_date, decision_at
        return quantile_returns(
            cross_section.future_returns_by_asset,
            quantile_count,
            cross_section.factor_values_by_asset,
            cross_section.weights_by_asset,
        )

    def future_returns(
        self,
        cross_section: CrossSection,
        holding_period: int,
        factor_date: date,
        decision_at: datetime,
    ) -> MetricPoint:
        results = calculate_future_returns(
            factor_date,
            decision_at,
            holding_period,
            cross_section.valuation_endpoints_by_asset,
        )
        valid_results = [result for result in results if result.status == "OK"]
        value = _weighted_mean_results(valid_results, cross_section.weights_by_asset)
        return MetricPoint(
            factor_date=factor_date,
            decision_at=decision_at,
            status="OK" if value is not None else "UNDEFINED",
            value=value,
            aligned_count=len(valid_results),
            missing_count=len(results) - len(valid_results),
            details=("future-return-undefined",) if value is None else (),
        )

    def rank_autocorrelation(
        self,
        previous_values_by_asset: Mapping[str, Decimal],
        current_values_by_asset: Mapping[str, Decimal],
        factor_date: date,
        decision_at: datetime,
    ) -> MetricPoint:
        shared_assets = sorted(set(previous_values_by_asset) & set(current_values_by_asset))
        previous_values = [previous_values_by_asset[asset_id] for asset_id in shared_assets]
        current_values = [current_values_by_asset[asset_id] for asset_id in shared_assets]
        previous_ranks = domain_average_tie_rank(previous_values)
        current_ranks = domain_average_tie_rank(current_values)
        if previous_ranks is None or current_ranks is None:
            return MetricPoint(
                factor_date=factor_date,
                decision_at=decision_at,
                status="UNDEFINED",
                value=None,
                aligned_count=len(shared_assets),
                details=("rank-autocorrelation-undefined",),
            )
        result = pearson_information_coefficient(previous_ranks, current_ranks)
        return _correlation_point(
            factor_date,
            decision_at,
            result,
            len(shared_assets),
            "rank-autocorrelation",
        )

    def turnover(
        self,
        previous_weights_by_asset: Mapping[str, Decimal],
        current_weights_by_asset: Mapping[str, Decimal],
        factor_date: date,
        decision_at: datetime,
    ) -> MetricPoint:
        return _turnover_point(
            previous_weights_by_asset,
            current_weights_by_asset,
            factor_date,
            decision_at,
        )

    def get_evaluation(self, request: FactorEvaluationRequest) -> FactorEvaluationResult:
        return domain_evaluate_factor_request(request)

    def get_info_coefficient(
        self,
        samples: Sequence[FactorSample],
        value_by_currency: Mapping[str, Decimal],
        factor_date: date,
    ) -> MetricPoint:
        if not samples:
            return _undefined_point(
                factor_date,
                datetime(1970, 1, 1),
                "annualized-information-coefficient-undefined",
            )
        relevant_samples = [sample for sample in samples if sample.factor_date == factor_date]
        if not relevant_samples:
            return _undefined_point(
                factor_date,
                datetime(1970, 1, 1),
                "annualized-information-coefficient-undefined",
            )
        decision_at = relevant_samples[0].decision_at
        factor_sample = relevant_samples[0]
        return self.pearson_information_coefficient(
            factor_sample.cross_section.factor_values_by_asset,
            factor_sample.cross_section.future_returns_by_asset,
            factor_date,
            decision_at,
        )

    def get_factor_annualized_information_coefficient(
        self,
        samples: Sequence[FactorSample],
        decayed_weights_by_sample: Sequence[Mapping[str, Decimal]],
        base_rate: Decimal,
    ) -> MetricPoint | None:
        if not samples or not decayed_weights_by_sample:
            return None
        stored_sample = samples[0]
        decayed_weights: dict[str, Decimal] = {}
        for sample, weights in zip(samples, decayed_weights_by_sample, strict=True):
            stored_sample = sample
            for asset_id, weight in weights.items():
                decayed_weights[asset_id] = decayed_weights.get(asset_id, Decimal(0)) + weight
        assets = sorted(decayed_weights)
        combined_values = [decayed_weights[asset_id] for asset_id in assets]
        factor_values: list[Decimal] = []
        for asset_id in assets:
            value = stored_sample.cross_section.factor_values_by_asset.get(asset_id)
            if value is not None:
                factor_values.append(value)
            else:
                factor_values.append(Decimal(0))
        result = pearson_information_coefficient(
            factor_values,
            [factor_values[index] * combined_values[index] for index in range(len(factor_values))],
        )
        if not isinstance(result, Decimal):
            return None
        annualized_value = (
            (Decimal(1) + result * base_rate).copy_abs()
            ** Decimal(str(samples[-1].factor_date - samples[0].factor_date).split()[0])
        ) - Decimal(1)
        return _correlation_point(
            samples[-1].factor_date,
            samples[-1].decision_at,
            annualized_value,
            len(factor_values),
            "annualized-information-coefficient",
        )

    def evaluate_factor_pearson_information_coefficient(
        self,
        factor_values_by_asset: Mapping[str, Decimal],
        future_returns_by_asset: Mapping[str, Decimal | None],
        factor_date: date,
        decision_at: datetime,
    ) -> MetricPoint:
        return self.pearson_information_coefficient(
            factor_values_by_asset,
            future_returns_by_asset,
            factor_date,
            decision_at,
        )

    def evaluate_factor_spearman_information_coefficient(
        self,
        factor_values_by_asset: Mapping[str, Decimal],
        future_returns_by_asset: Mapping[str, Decimal | None],
        factor_date: date,
        decision_at: datetime,
    ) -> MetricPoint:
        return self.spearman_information_coefficient(
            factor_values_by_asset,
            future_returns_by_asset,
            factor_date,
            decision_at,
        )


FactorService = FactorEvaluationService


def _aligned_values(
    factor_values_by_asset: Mapping[str, Decimal],
    future_returns_by_asset: Mapping[str, Decimal | None],
) -> tuple[list[Decimal], list[Decimal]]:
    shared_assets = sorted(set(factor_values_by_asset) & set(future_returns_by_asset))
    factor_values: list[Decimal] = []
    future_returns: list[Decimal] = []
    for asset_id in shared_assets:
        factor_value = factor_values_by_asset[asset_id]
        future_return = future_returns_by_asset[asset_id]
        if future_return is None:
            continue
        factor_values.append(factor_value)
        future_returns.append(future_return)
    return factor_values, future_returns


def _correlation_point(
    factor_date: date,
    decision_at: datetime,
    result: CorrelationStatus | Decimal,
    aligned_count: int,
    name: str,
) -> MetricPoint:
    return MetricPoint(
        factor_date=factor_date,
        decision_at=decision_at,
        status=result if isinstance(result, str) else "OK",
        value=result if isinstance(result, Decimal) else None,
        aligned_count=aligned_count,
        details=(f"{name}-undefined",) if not isinstance(result, Decimal) else (),
    )


def _undefined_point(
    factor_date: date,
    decision_at: datetime,
    detail: str,
) -> MetricPoint:
    return MetricPoint(
        factor_date=factor_date,
        decision_at=decision_at,
        status="UNDEFINED",
        value=None,
        details=(detail,),
    )


def _weighted_mean_results(
    results: Sequence[object],
    weights_by_asset: Mapping[str, Decimal | None],
) -> Decimal | None:
    if not results:
        return None
    total_weight = Decimal(0)
    weighted_sum = Decimal(0)
    for result in results:
        future_return = getattr(result, "value", None)
        asset_id = getattr(result, "canonical_asset_id", "")
        if future_return is None or not isinstance(future_return, Decimal):
            continue
        weight = weights_by_asset.get(asset_id, Decimal(1))
        if weight is None or not weight.is_finite() or weight < 0:
            continue
        total_weight += weight
        weighted_sum += weight * future_return
    if total_weight == 0:
        return None
    return weighted_sum / total_weight


def _turnover_point(
    previous_weights_by_asset: Mapping[str, Decimal],
    current_weights_by_asset: Mapping[str, Decimal],
    factor_date: date,
    decision_at: datetime,
) -> MetricPoint:
    zero = Decimal(0)
    asset_ids = sorted(set(previous_weights_by_asset) | set(current_weights_by_asset))
    turnover = sum(
        (
            abs(current_weights_by_asset.get(asset_id, zero) - previous_weights_by_asset.get(asset_id, zero))
            for asset_id in asset_ids
        ),
        Decimal(0),
    ) / Decimal(2)
    return MetricPoint(
        factor_date=factor_date,
        decision_at=decision_at,
        status="OK",
        value=turnover,
        aligned_count=len(asset_ids),
    )
