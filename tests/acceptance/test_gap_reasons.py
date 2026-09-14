from __future__ import annotations

from mmqp.application.queries import SUPPORTED_QUERY_FILTERS


def test_query_datasets_closed():
    assert "DAILY_BAR" in SUPPORTED_QUERY_FILTERS
