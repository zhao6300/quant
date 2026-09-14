from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext

from mmqp.domain.errors import DomainError, ProblemV1


class PortfolioDependencyError(DomainError):
    def __init__(self, detail: str):
        super().__init__(
            ProblemV1(
                kind="portfolio/dependency-failed",
                title="Portfolio dependency failed",
                status=400,
                detail=detail,
            )
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioDefinition:
    definition_id: str
    version_id: str
    universe_id: str
    factor_definition_id: str
    factor_definition_version_id: str
    factor_position_date: int
    index_policy_id: str
    group_amount: Decimal
    enabled: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class DeterministicPortfolio:
    portfolio_id: str
    definition_id: str
    weights_by_asset: tuple[tuple[str, Decimal], ...]
    dependency_schema_version: str
    definition_json: str
    definition_data: str
    definition_data_hash: str


def build_score_weighted_portfolio(
    scores_by_asset: dict[str, tuple[Decimal | None, str | None, int]],
) -> DeterministicPortfolio:
    with localcontext() as context:
        context.prec = 80
        total = Decimal(0)
        for _asset_id, (score, _group, _count) in sorted(scores_by_asset.items()):
            if score is None:
                continue
            total += score
        if total <= 0:
            raise PortfolioDependencyError("score sum is not positive")
        weights: list[tuple[str, Decimal]] = []
        for asset_id, (score, _group, _count) in sorted(scores_by_asset.items()):
            if score is None:
                continue
            weight = score / total
            weights.append((asset_id, weight))
        actual_total = sum((weight for _asset_id, weight in weights), Decimal(0))
        if actual_total != Decimal(1):
            residual = Decimal(1) - actual_total
            largest_index = max(range(len(weights)), key=lambda index: weights[index][1])
            asset_id, weight = weights[largest_index]
            weights[largest_index] = (asset_id, weight + residual)
        validate_weights(tuple(weights))
        validate_weights(tuple(weights))
    return DeterministicPortfolio(
        portfolio_id="portfolio",
        definition_id="score-weighted",
        weights_by_asset=tuple(weights),
        dependency_schema_version="portfolio-score-weighted-v1",
        definition_json="{}",
        definition_data="{}",
        definition_data_hash="{}",
    )


def validate_weights(weights: tuple[tuple[str, Decimal], ...]) -> None:
    total = sum((weight for _asset_id, weight in weights), Decimal(0))
    if total != Decimal(1):
        raise PortfolioDependencyError("portfolio weights do not sum to one")
    if any(weight < 0 for _asset_id, weight in weights):
        raise PortfolioDependencyError("portfolio weights must be non-negative")
