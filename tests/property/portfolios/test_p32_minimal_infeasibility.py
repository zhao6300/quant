from __future__ import annotations

from itertools import combinations

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.kernels.infeasibility import LinearConstraint, find_minimum_infeasible_subset


def _constraints_from_intervals(intervals: list[tuple[int, int]]) -> list[LinearConstraint]:
    return tuple(
        LinearConstraint(
            constraint_id=index,
            variables=("asset",),
            coefficients=(1,),
            lower_bound=lower,
            upper_bound=upper,
        )
        for index, (lower, upper) in enumerate(intervals)
    )


@settings(max_examples=100, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(-6, 6), st.integers(-6, 6)).filter(lambda pair: pair[0] <= pair[1]),
        min_size=2,
        max_size=6,
    ).map(_constraints_from_intervals)
)
def test_p32_minimal_infeasibility_is_exact_and_atomic(constraints: tuple[LinearConstraint, ...]) -> None:
    """Property 32: the first returned subset is exhaustive-minimal and leaves state unchanged."""

    expected: tuple[int, ...] | None = None
    for cardinality in range(1, len(constraints) + 1):
        for selected_ids in combinations(
            (constraint.constraint_id for constraint in constraints), cardinality
        ):
            selected = [constraint for constraint in constraints if constraint.constraint_id in selected_ids]
            if max(constraint.lower_bound for constraint in selected) > min(
                constraint.upper_bound for constraint in selected
            ):
                expected = selected_ids
                break
        if expected is not None:
            break

    snapshot_before = tuple(constraints)
    result = find_minimum_infeasible_subset(constraints)
    snapshot_after = tuple(constraints)

    assert result == expected
    assert snapshot_before == snapshot_after
