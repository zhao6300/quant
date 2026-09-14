from __future__ import annotations

from decimal import Decimal
from itertools import combinations

import pytest

from mmqp.kernels.infeasibility import LinearConstraint, find_minimum_infeasible_subset


def constraint(constraint_id: int, lower: Decimal, upper: Decimal) -> LinearConstraint:
    return LinearConstraint(constraint_id, ("a",), (Decimal(1),), lower, upper)


def test_returns_first_ascending_minimum_infeasible_subset() -> None:
    constraints = [
        constraint(7, Decimal(4), Decimal(8)),
        constraint(2, Decimal(2), Decimal(2)),
        constraint(5, Decimal(0), Decimal(2)),
    ]
    assert find_minimum_infeasible_subset(constraints) == (2, 7)


def test_conflict_requires_two_constraints() -> None:
    constraints = [
        constraint(1, Decimal(0), Decimal(2)),
        constraint(4, Decimal(-2), Decimal(-1)),
    ]
    assert find_minimum_infeasible_subset(constraints) == (1, 4)


def test_feasible_system_has_no_infeasible_subset() -> None:
    constraints = [
        constraint(3, Decimal(0), Decimal(2)),
        constraint(6, Decimal(0), Decimal(1)),
        constraint(9, Decimal(-1), Decimal(3)),
    ]
    assert find_minimum_infeasible_subset(constraints) is None


def test_exhaustive_small_system_matches_oracle() -> None:
    constraints = [
        constraint(1, Decimal(0), Decimal(1)),
        constraint(2, Decimal(1), Decimal(1)),
        constraint(3, Decimal(2), Decimal(3)),
        constraint(4, Decimal(-10), Decimal(10)),
    ]

    def is_infeasible(constraint_ids: tuple[int, ...]) -> bool:
        selected = [item for item in constraints if item.constraint_id in constraint_ids]
        return max(item.lower_bound for item in selected) > min(item.upper_bound for item in selected)

    for cardinality in range(1, len(constraints) + 1):
        for selected_ids in combinations((item.constraint_id for item in constraints), cardinality):
            if is_infeasible(selected_ids):
                assert find_minimum_infeasible_subset(constraints) == selected_ids
                return
    raise AssertionError("expected an infeasible subset")


def test_repeated_calls_reproduce_result() -> None:
    constraints = [
        constraint(1, Decimal(0), Decimal(1)),
        constraint(4, Decimal(2), Decimal(3)),
    ]
    first = find_minimum_infeasible_subset(constraints)
    second = find_minimum_infeasible_subset(constraints)
    assert first == second == (1, 4)


def test_duplicate_identifiers_are_rejected() -> None:
    constraints = [
        constraint(1, Decimal(0), Decimal(1)),
        constraint(1, Decimal(0), Decimal(0)),
    ]
    with pytest.raises(ValueError, match="unique"):
        find_minimum_infeasible_subset(constraints)
