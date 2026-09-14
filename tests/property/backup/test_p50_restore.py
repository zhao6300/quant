from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mmqp.adapters.backup import needs_rollback


@given(manifest_id=st.sampled_from(("m-1", "empty")), includes_credentials=st.booleans())
def test_preserves_valid_support(manifest_id, includes_credentials):
    valid_manifest_id = manifest_id != "empty"
    if includes_credentials:
        with pytest.raises(Exception, match="credentials"):
            needs_rollback(manifest_id, True)
    elif not valid_manifest_id:
        with pytest.raises(Exception, match="credentials"):
            needs_rollback(manifest_id, includes_credentials=True)
    else:
        assert needs_rollback(manifest_id, includes_credentials) is not valid_manifest_id
