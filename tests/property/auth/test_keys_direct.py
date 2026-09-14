from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from tests.helpers.queries import can_run_queries


@given(endpoint=st.sampled_from(("reports", "pulls", "invalid")))
def test_response_fits(endpoint):
    assert can_run_queries(endpoint) is True
