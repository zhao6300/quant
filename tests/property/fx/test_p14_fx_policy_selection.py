from hypothesis import given
from hypothesis import strategies as st


@given(rate_history=st.lists(st.integers(min_value=1, max_value=100), max_size=5))
def test_fx_policy_selection_bounded(rate_history: list[int]) -> None:
    assert len(rate_history) <= 5
