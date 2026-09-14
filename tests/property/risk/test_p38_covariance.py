from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.domain.risk import CovarianceMatrix, covariance_contributions


@settings(max_examples=100)
@given(valueA=st.integers(min_value=1, max_value=10), valueB=st.integers(min_value=1, max_value=10))
def test_covariance_contributions_reconcile(valueA: int, valueB: int) -> None:
    a = Decimal(valueA) / Decimal(10)
    b = Decimal(valueB) / Decimal(10)
    matrix = CovarianceMatrix(
        holdings=("A", "B"),
        values=(
            (a, Decimal("0.01")),
            (Decimal("0.01"), b),
        ),
    )
    contributions = covariance_contributions(matrix, {"A": Decimal(1), "B": Decimal(0)})
    assert contributions.portfolio_variance == a
    assert contributions.marginal_variance["A"] == a
    assert contributions.component_variance["A"] == a
    assert abs(contributions.residual) <= Decimal("1e-10")


@settings(max_examples=100)
@given(valueA=st.integers(min_value=1, max_value=10), valueB=st.integers(min_value=1, max_value=10))
def test_rejects_non_symmetric_and_misaligned_matrix(valueA: int, valueB: int) -> None:
    a = Decimal(valueA) / Decimal(10)
    b = Decimal(valueB) / Decimal(10)
    matrix = CovarianceMatrix(
        holdings=("A", "B"),
        values=(
            (a, Decimal("0.01")),
            (Decimal("0.01"), b),
        ),
    )
    try:
        covariance_contributions(matrix, {"A": Decimal(1), "B": Decimal(0), "C": Decimal(0)})
    except ValueError as error:
        assert "weights must exactly match covariance holdings" in str(error)
    else:
        pytest.fail("misaligned covariance weights were accepted")
