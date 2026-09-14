from __future__ import annotations

from mmqp.adapters.backup import needs_rollback


def test_restorable_state_verification():
    assert needs_rollback("all-attached", False) is False
