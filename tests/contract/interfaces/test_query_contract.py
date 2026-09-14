from __future__ import annotations

from mmqp.application.queries import SUPPORTED_QUERY_FILTERS


def test_interface_dataset_allowlist_is_closed():
    assert "DAILY_BAR" in SUPPORTED_QUERY_FILTERS
    assert "broker_order" not in SUPPORTED_QUERY_FILTERS
