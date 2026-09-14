from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.domain.quality import RejectedConfirmation


@settings(max_examples=16, deadline=None)
@given(
    exact_snapshot=st.booleans(),
    exact_set=st.booleans(),
)
def test_rejected_confirmation_must_be_exact_and_complete(exact_snapshot: bool, exact_set: bool) -> None:
    confirmation = _confirmation(exact_snapshot, exact_set)
    expected = _confirmation(True, True)

    assert (confirmation == expected) == (exact_snapshot and exact_set)


def _confirmation(snapshot_id: bool, version_ids: bool) -> RejectedConfirmation:
    return RejectedConfirmation(
        snapshot_id="snapshot-1" if snapshot_id else "other-snapshot",
        rejected_version_ids=frozenset({"rejected-1", "rejected-2"} if version_ids else {"rejected-1"}),
    )
