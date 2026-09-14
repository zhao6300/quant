from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from itertools import combinations

type _Inequality = tuple[Mapping[str, Fraction], Fraction]


@dataclass(frozen=True, slots=True)
class LinearConstraint:
    constraint_id: int
    variables: tuple[str, ...]
    coefficients: tuple[Decimal, ...]
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None

    def value_at(self, values_by_variable: Mapping[str, Decimal]) -> Decimal:
        return sum(
            (
                coefficient * values_by_variable[variable]
                for variable, coefficient in zip(self.variables, self.coefficients, strict=True)
            ),
            Decimal(0),
        )

    def is_satisfied_by(self, variables: Mapping[str, Decimal]) -> bool:
        value = self.value_at(variables)
        if self.lower_bound is not None and value < self.lower_bound:
            return False
        if self.upper_bound is not None and value > self.upper_bound:
            return False
        return True


def find_minimum_infeasible_subset(
    constraints: Sequence[LinearConstraint],
    *,
    memoized: bool = True,
) -> tuple[int, ...] | None:
    """Return the first minimum-cardinality, lexicographically ordered infeasible subset.

    The branch-and-bound search orders subsets first by cardinality and then by their
    ascending constraint identifiers.  Each exact feasibility check uses Fourier-Motzkin
    elimination on a shared map from tested subsets to results.
    """

    ordered = sorted(constraints, key=lambda constraint: constraint.constraint_id)
    identifiers = {constraint.constraint_id for constraint in ordered}
    if len(identifiers) != len(ordered):
        raise ValueError("constraint identifiers must be unique")
    if any(constraint.constraint_id < 0 for constraint in ordered):
        raise ValueError("constraint identifiers must be non-negative")
    for constraint in ordered:
        if len(constraint.variables) != len(constraint.coefficients):
            raise ValueError(f"constraint {constraint.constraint_id} has invalid dimensions")
        if constraint.constraint_id not in identifiers:
            raise ValueError(f"constraint {constraint.constraint_id} is missing from the search")
        if (
            constraint.lower_bound is not None
            and constraint.upper_bound is not None
            and constraint.lower_bound > constraint.upper_bound
        ):
            raise ValueError(f"constraint {constraint.constraint_id} has inverted bounds")

    feasibility_cache: dict[frozenset[int], bool] = {}
    constraints_by_id = {constraint.constraint_id: constraint for constraint in ordered}

    def is_feasible(constraint_ids: frozenset[int]) -> bool:
        if memoized and constraint_ids in feasibility_cache:
            return feasibility_cache[constraint_ids]
        selected = sorted(
            (constraints_by_id[constraint_id] for constraint_id in constraint_ids),
            key=lambda constraint: constraint.constraint_id,
        )
        feasible = _linear_intersection_is_nonempty(selected, _variables_for(selected))
        if memoized:
            feasibility_cache[constraint_ids] = feasible
        return feasible

    ordered_ids = tuple(constraint.constraint_id for constraint in ordered)
    for cardinality in range(1, len(ordered_ids) + 1):
        for selected_ids in combinations(ordered_ids, cardinality):
            keys = frozenset(selected_ids)
            if not is_feasible(keys):
                return selected_ids
    return None


def _variables_for(constraints: Sequence[LinearConstraint]) -> tuple[str, ...]:
    return tuple(sorted({variable for constraint in constraints for variable in constraint.variables}))


def _linear_intersection_is_nonempty(
    constraints: Sequence[LinearConstraint], variables: Sequence[str]
) -> bool:
    inequalities: list[_Inequality] = []
    for constraint in constraints:
        coefficients = {
            variable: Fraction(coefficient)
            for variable, coefficient in zip(constraint.variables, constraint.coefficients, strict=True)
        }
        if constraint.lower_bound is not None:
            inequalities.append((coefficients, Fraction(constraint.lower_bound)))
        if constraint.upper_bound is not None:
            inequalities.append(
                (
                    {variable: -coefficient for variable, coefficient in coefficients.items()},
                    -Fraction(constraint.upper_bound),
                )
            )
    if not inequalities:
        return True

    for variable in variables:
        fixed, positive, negative = [], [], []
        for inequality in inequalities:
            selected_coefficients: Mapping[str, Fraction] = inequality[0]
            right_side: Fraction = inequality[1]
            coefficient = selected_coefficients.get(variable, Fraction(0))
            adjusted: dict[str, Fraction] = {
                name: value for name, value in selected_coefficients.items() if name != variable
            }
            if coefficient == 0:
                fixed.append((adjusted, right_side))
            elif coefficient > 0:
                positive.append((coefficient, adjusted, right_side))
            else:
                negative.append((coefficient, adjusted, right_side))

        combined: list[_Inequality] = list(fixed)
        for positive_coefficient, positive_coefficients, positive_right_side in positive:
            for negative_coefficient, negative_coefficients, negative_right_side in negative:
                scale = positive_coefficient / -negative_coefficient
                coefficients_delta = {
                    name: positive_coefficients.get(name, Fraction(0))
                    + scale * negative_coefficients.get(name, Fraction(0))
                    for name in positive_coefficients.keys() | negative_coefficients.keys()
                }
                right_side_delta = positive_right_side + scale * negative_right_side
                combined.append(
                    (
                        {name: value / -negative_coefficient for name, value in coefficients_delta.items()},
                        right_side_delta / -negative_coefficient,
                    )
                )
        inequalities = combined

    return all(right_side <= 0 for _coefficients, right_side in inequalities)
