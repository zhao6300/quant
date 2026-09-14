from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from mmqp.adapters.backup import needs_rollback


@given(manifest_id=st.sampled_from(("m-1", "empty")), includes_credentials=st.booleans())
def test_union(manifest_id, includes_credentials):
    if manifest_id and not includes_credentials:
        assert needs_rollback(manifest_id, False) is False
