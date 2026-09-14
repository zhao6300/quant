from __future__ import annotations

from dataclasses import dataclass

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.backends import TypedQuery


@dataclass(frozen=True, slots=True)
class _Source:
    value: int


@given(value=st.integers(min_value=1, max_value=100))
def test_interface_mapping(value):
    query = TypedQuery.from_filter(value)
    assert query.filters == ()
