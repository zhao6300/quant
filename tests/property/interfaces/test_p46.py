from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.backends import LIMITS


@given(limit=st.sampled_from(LIMITS))
def test_results_bounded(limit):
    assert limit < 1000
