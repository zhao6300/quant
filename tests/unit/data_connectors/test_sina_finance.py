from __future__ import annotations

from datetime import date

from mmqp.adapters.data_connectors.sina_finance import SinaFinanceDailyBarConnector


class _FakeTransport:
    def __init__(self, response: object) -> None:
        self._response = response

    def text(self, _: str) -> str:
        return self._response


def test_returns_requested_daily_bar() -> None:
    connector = SinaFinanceDailyBarConnector(
        transport=_FakeTransport(
            '[{"day": "2026-09-11", "open": "1", "high": "2", "low": "0.5", "close": "1.5", "volume": "10"},'
            '{"day": "2026-09-12", "open": "1.5", "high": "2", "low": "0.5", "close": "1.5", "volume": "10"}]'
        ),
    )
    bar = connector.fetch(provider_code="600000.SS", trading_date=date(2026, 9, 12))
    assert bar.open == 1.5
