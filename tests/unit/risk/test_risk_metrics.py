from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from mmqp.domain.risk import (
    CovarianceMatrix,
    ReturnSample,
    ValuationPoint,
    annualized_volatility,
    beta,
    concentration,
    covariance_contributions,
    maximum_drawdown,
    tracking_error,
)


def _sample(
    start_year: int,
    end_year: int,
    portfolio: str,
    benchmark: str | None,
) -> ReturnSample:
    return ReturnSample(
        start=datetime(start_year, 1, 1, tzinfo=UTC),
        end=datetime(end_year, 1, 1, tzinfo=UTC),
        portfolio=Decimal(portfolio),
        benchmark=None if benchmark is None else Decimal(benchmark),
    )


def test_volatility_equals_reference_formula() -> None:
    samples = (_sample(2024, 2025, "0.1", "0.1"), _sample(2025, 2026, "-0.1", "-0.1"))
    value = annualized_volatility(samples, Decimal(252))
    expected = (Decimal("0.02") * Decimal(252)).sqrt()
    assert abs(value - expected) < Decimal("1e-14")


def test_maximum_drawdown_uses_prefix_peak() -> None:
    values = (
        ValuationPoint(datetime(2024, 1, 1, tzinfo=UTC), Decimal("100")),
        ValuationPoint(datetime(2024, 2, 1, tzinfo=UTC), Decimal("80")),
        ValuationPoint(datetime(2024, 3, 1, tzinfo=UTC), Decimal("120")),
    )
    assert maximum_drawdown(values) == Decimal("0.2")


def test_tracking_error_and_beta() -> None:
    samples = (
        _sample(2024, 2025, "0.2", "0.1"),
        _sample(2025, 2026, "-0.1", "-0.2"),
    )
    assert tracking_error(samples, Decimal(252)) == Decimal(0)
    assert beta(samples) == Decimal("1")


def test_beta_is_undefined_with_zero_benchmark_variance() -> None:
    samples = (
        _sample(2024, 2025, "0.2", "0.1"),
        _sample(2025, 2026, "-0.1", "0.1"),
    )
    assert beta(samples) is None


def test_covariance_contributions_reconcile() -> None:
    matrix = CovarianceMatrix(
        holdings=("A", "B"),
        values=((Decimal("0.04"), Decimal("0.01")), (Decimal("0.01"), Decimal("0.02"))),
    )
    contributions = covariance_contributions(matrix, {"A": Decimal("0.5"), "B": Decimal("0.5")})
    assert contributions.portfolio_variance == Decimal("0.02")
    assert abs(contributions.residual) <= Decimal("1e-10")


def test_misaligned_covariance_matrix_is_rejected() -> None:
    matrix = CovarianceMatrix(
        holdings=("A", "B"),
        values=((Decimal("0.04"), Decimal("0.01")), (Decimal("0.01"), Decimal("0.02"))),
    )
    with pytest.raises(ValueError, match="weights must exactly match covariance holdings"):
        covariance_contributions(
            matrix,
            {"A": Decimal("1"), "B": Decimal("0"), "C": Decimal("0")},
        )


def test_concentration_uses_weights_and_classifications() -> None:
    values = {"A": Decimal("3"), "B": Decimal("1")}
    value = concentration(
        values,
        {"A": "US", "B": "US"},
        {"A": "TECH", "B": "FINANCE"},
        {"A": "USD", "B": "USD"},
    )
    assert value.single == Decimal("0.75")
    assert value.top_five == Decimal("1")
    assert value.markets == {"US": Decimal("1")}
    assert value.industries == {"FINANCE": Decimal("0.25"), "TECH": Decimal("0.75")}
    assert value.currencies == {"USD": Decimal("1")}
