from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import numpy as np


@dataclass(frozen=True, slots=True)
class ReturnSample:
    start: datetime
    end: datetime
    portfolio: Decimal
    benchmark: Decimal | None = None

    def validate(self) -> None:
        if self.start >= self.end:
            raise ValueError("return sample timestamps must be increasing")
        if not self.portfolio.is_finite():
            raise ValueError("portfolio return must be finite")
        if self.benchmark is not None and not self.benchmark.is_finite():
            raise ValueError("benchmark return must be finite")


@dataclass(frozen=True, slots=True)
class ValuationPoint:
    timestamp: datetime
    value: Decimal

    def validate(self) -> None:
        if not self.value.is_finite() or self.value <= 0:
            raise ValueError("valuation must be finite and positive")


@dataclass(frozen=True, slots=True)
class CovarianceMatrix:
    holdings: tuple[str, ...]
    values: tuple[tuple[Decimal, ...], ...]

    def validate(self) -> None:
        if len(self.holdings) != len(set(self.holdings)):
            raise ValueError("covariance holdings must be unique")
        if len(self.values) != len(self.holdings):
            raise ValueError("covariance matrix is not square")
        if any(len(row) != len(self.holdings) for row in self.values):
            raise ValueError("covariance matrix is misaligned")
        if any(not value.is_finite() for row in self.values for value in row):
            raise ValueError("covariance matrix contains non-finite values")
        if any(
            abs(self.values[row_index][column_index] - self.values[column_index][row_index])
            > Decimal("1e-12")
            for row_index in range(len(self.holdings))
            for column_index in range(len(self.holdings))
        ):
            raise ValueError("covariance matrix is not symmetric")
        diagonal = (self.values[index][index] for index in range(len(self.holdings)))
        scale = max((abs(value) for value in diagonal), default=Decimal(0))
        tolerance = Decimal("1e-12") * max(Decimal(1), scale)
        np_row = [tuple(float(value) for value in row) for row in self.values]
        smallest_eigenvalue = min(float(value) for value in np.linalg.eigvalsh(np.asarray(np_row)))
        if Decimal(smallest_eigenvalue) < tolerance:
            raise ValueError("covariance matrix is not positive semidefinite")


def aligned_return_samples(
    samples: Sequence[ReturnSample],
    require_benchmark: bool,
) -> tuple[ReturnSample, ...]:
    aligned: list[ReturnSample] = []
    for sample in sorted(samples, key=lambda item: (item.start, item.end)):
        sample.validate()
        if require_benchmark and sample.benchmark is not None:
            aligned.append(sample)
        elif not require_benchmark:
            aligned.append(sample)
    return tuple(aligned)


def annualized_volatility(samples: Sequence[ReturnSample], factor: Decimal) -> Decimal:
    if not Decimal(0) < factor <= Decimal(366):
        raise ValueError("annualization factor must be between zero and 366")
    aligned = aligned_return_samples(samples, require_benchmark=False)
    portfolio = [sample.portfolio for sample in aligned]
    if len(portfolio) < 2:
        raise ValueError("volatility requires two aligned return samples")
    mean = sum(portfolio, Decimal(0)) / Decimal(len(portfolio))
    variance = sum((value - mean) * (value - mean) for value in portfolio) / Decimal(
        len(portfolio) - 1
    )
    return (variance * factor).sqrt()


def maximum_drawdown(values: Sequence[ValuationPoint]) -> Decimal:
    ordered = sorted(values, key=lambda point: point.timestamp)
    for point in ordered:
        point.validate()
    if not ordered:
        raise ValueError("maximum drawdown requires one valuation")
    peak = ordered[0].value
    maximum = Decimal(0)
    for point in ordered:
        peak = max(peak, point.value)
        maximum = max(maximum, Decimal(1) - point.value / peak)
    return maximum


def tracking_error(samples: Sequence[ReturnSample], factor: Decimal) -> Decimal:
    if not Decimal(0) < factor <= Decimal(366):
        raise ValueError("annualization factor must be between zero and 366")
    aligned = aligned_return_samples(samples, require_benchmark=True)
    differences = [
        sample.portfolio - (sample.benchmark if sample.benchmark is not None else Decimal(0))
        for sample in aligned
        if sample.benchmark is not None
    ]
    if len(differences) < 2:
        raise ValueError("tracking error requires two aligned return samples")
    mean = sum(differences, Decimal(0)) / Decimal(len(differences))
    variance = sum((difference - mean) * (difference - mean) for difference in differences) / Decimal(
        len(differences) - 1
    )
    return (variance * factor).sqrt()


def beta(samples: Sequence[ReturnSample]) -> Decimal | None:
    aligned = aligned_return_samples(samples, require_benchmark=True)
    aligned_pairs = [sample for sample in aligned if sample.benchmark is not None]
    if len(aligned_pairs) < 2:
        return None
    portfolio = [sample.portfolio for sample in aligned_pairs]
    benchmark: list[Decimal] = [
        sample.benchmark if sample.benchmark is not None else Decimal(0)
        for sample in aligned_pairs
    ]
    portfolio_mean = sum(portfolio, Decimal(0)) / Decimal(len(portfolio))
    benchmark_mean = sum(benchmark, Decimal(0)) / Decimal(len(benchmark))
    benchmark_variance: Decimal = sum(
        ((value - benchmark_mean) * (value - benchmark_mean) for value in benchmark),
        Decimal(0),
    )
    if benchmark_variance <= Decimal(0):
        return None
    covariance: Decimal = sum(
        (
            (portfolio[index] - portfolio_mean) * (benchmark[index] - benchmark_mean)
            for index in range(len(portfolio))
        ),
        Decimal(0),
    )
    return covariance / benchmark_variance


@dataclass(frozen=True, slots=True)
class CovarianceContributions:
    portfolio_variance: Decimal
    marginal_variance: dict[str, Decimal]
    component_variance: dict[str, Decimal]
    component_volatility: dict[str, Decimal]
    residual: Decimal


def covariance_contributions(
    matrix: CovarianceMatrix,
    weights: Mapping[str, Decimal],
) -> CovarianceContributions:
    matrix.validate()
    held = tuple(sorted(weights))
    if held != matrix.holdings:
        raise ValueError("weights must exactly match covariance holdings")
    marginal: dict[str, Decimal] = {}
    for row_index, holding in enumerate(matrix.holdings):
        marginal[holding] = sum(
            (matrix.values[row_index][column_index] * weights[row_name]
             for column_index, row_name in enumerate(matrix.holdings)),
            Decimal(0),
        )
    component_variance = {
        holding: weights[holding] * marginal[holding] for holding in matrix.holdings
    }
    portfolio_variance = sum(component_variance.values(), Decimal(0))
    if portfolio_variance <= Decimal(0):
        raise ValueError("portfolio variance is not positive")
    volatility = portfolio_variance.sqrt()
    component_volatility = {
        holding: component_variance[holding] / volatility for holding in matrix.holdings
    }
    residual = sum(component_variance.values(), Decimal(0)) - portfolio_variance
    if abs(residual) > Decimal("1e-10") * max(Decimal(1), abs(portfolio_variance)):
        raise ValueError("covariance contribution residual exceeds tolerance")
    return CovarianceContributions(
        portfolio_variance=portfolio_variance,
        marginal_variance=marginal,
        component_variance=component_variance,
        component_volatility=component_volatility,
        residual=residual,
    )


@dataclass(frozen=True, slots=True)
class Concentration:
    single: Decimal
    top_five: Decimal
    markets: dict[str, Decimal]
    industries: dict[str, Decimal]
    currencies: dict[str, Decimal]


def concentration(
    values: Mapping[str, Decimal],
    markets: Mapping[str, str],
    industries: Mapping[str, str],
    currencies: Mapping[str, str],
) -> Concentration:
    if any(not value.is_finite() or value <= 0 for value in values.values()):
        raise ValueError("market values must be finite and positive")
    total = sum(values.values(), Decimal(0))
    if total <= Decimal(0):
        raise ValueError("market value total must be positive")
    weights = {asset: value / total for asset, value in values.items()}
    sorted_weights = sorted(weights.values(), reverse=True)
    groups: dict[str, dict[str, Decimal]] = {
        "markets": {},
        "industries": {},
        "currencies": {},
    }
    classifications = [
        ("markets", markets),
        ("industries", industries),
        ("currencies", currencies),
    ]
    for group, mapping in classifications:
        for asset, weight in weights.items():
            if asset in mapping:
                key = mapping[asset]
                groups[group][key] = groups[group].get(key, Decimal(0)) + weight
    return Concentration(
        single=sum(sorted_weights[:1], Decimal(0)),
        top_five=sum(sorted_weights[:5], Decimal(0)),
        markets=groups["markets"],
        industries=groups["industries"],
        currencies=groups["currencies"],
    )
