from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from tests.helpers.redaction import redactions


@given(content=st.sampled_from(redactions["public"]), redact_id=st.booleans())
def test_content_redact(content, redact_id):
    assert content != redactions["credentials"]
