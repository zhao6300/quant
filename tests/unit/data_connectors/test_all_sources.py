from __future__ import annotations

from mmqp.adapters.data_connectors.registry import (
    CONNECTED_DAILY_BAR_SOURCES,
    CONNECTED_FUNDAMENTAL_FACT_SOURCES,
    daily_bar_endpoint_connectors,
)


class _FakeHTTPTransport:
    def __init__(self, response: object) -> None:
        self._response = response

    def json(self, _: str) -> object:
        return self._response


def test_all_registered_daily_bar_sources_are_listed() -> None:
    assert len(CONNECTED_DAILY_BAR_SOURCES) == 15
    assert set(daily_bar_endpoint_connectors()).issubset(set(CONNECTED_DAILY_BAR_SOURCES))
    assert CONNECTED_FUNDAMENTAL_FACT_SOURCES == ("sec-edgar", "fred")
