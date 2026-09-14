from __future__ import annotations

from mmqp.adapters.migration import pre_restore_check


def test_source_schema_is_compatible():
    assert pre_restore_check(10_000, 1) is True
