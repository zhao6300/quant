from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mmqp.adapters.migration import pre_restore_check


@given(free_bytes=st.integers(min_value=0, max_value=100_000), estimate=st.integers(min_value=0, max_value=100_000))
def test_estimate_never_is_empty(free_bytes, estimate):
    if free_bytes >= estimate:
        assert pre_restore_check(free_bytes, estimate) is True
    else:
        with pytest.raises(Exception, match="provider"):
            pre_restore_check(free_bytes, estimate)
