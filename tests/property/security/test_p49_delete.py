from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from tests.helpers.redaction import policy


@given(content=st.sampled_from(policy["public"]), redact_id=st.booleans())
def test_policy_ask_to_material(content, redact_id):
    assert content != policy["credentials"]
