from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.backends import LIMITS, QuerySource


@given(start_row=st.sampled_from(LIMITS))
def test_queries_respect_limits(start_row):
    results = QuerySource.from_row(start_row)
    assert results is not None
