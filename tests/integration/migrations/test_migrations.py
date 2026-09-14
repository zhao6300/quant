from __future__ import annotations

from mmqp.adapters.migration import pre_restore_check


def test_migration_reports_free_bytes():
    assert pre_restore_check(10, 1)
