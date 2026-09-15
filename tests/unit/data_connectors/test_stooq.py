from __future__ import annotations

from datetime import date
from decimal import Decimal
import pytest

from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.stooq import StooqDailyBarConnector
from mmqp.domain.providers import ProviderCategorizedError


class _FakeResponse:
    status = 200

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_stooq_connector_parses_a_single_daily_csv_row() -> None:
    expected_url = "https://stooq.com/q/d/l/?s=aapl.us&d1=2025-01-02&d2=2025-01-02&i=d"
    requested: list[str] = []

    def urlopen(url: str, timeout: float) -> _FakeResponse:
        requested.append(url)
        payload = (
            "Symbol,Date,Open,High,Low,Close,Volume\n"
            "AAPL.US,2025-01-02,236.11,236.11,225.31,225.91,52723500\n"
        )
        return _FakeResponse(payload.encode("utf-8"))

    observation = StooqDailyBarConnector(transport=HTTPTransport(urlopen)).fetch(
        provider_code="aapl.us",
        trading_date=date(2025, 1, 2),
    )

    assert requested == [expected_url]
    assert observation.open == Decimal("236.11")
    assert observation.high == Decimal("236.11")
    assert observation.low == Decimal("225.31")
    assert observation.close == Decimal("225.91")
    assert observation.volume == Decimal("52723500")
    assert observation.turnover == Decimal("0")
    assert observation.provider == "stooq"
    assert observation.trading_date == date(2025, 1, 2)
    assert observation.trading_currency == "USD"
    assert observation.provenance_id != ""


def test_stooq_connector_categorizes_a_bad_payload() -> None:
    def urlopen(_: str, __: float) -> _FakeResponse:
        return _FakeResponse(
            '<html><body>stooq.com requires JavaScript</body></html>'.encode("utf-8"),
        )

    with pytest.raises(ProviderCategorizedError) as error:
        StooqDailyBarConnector(transport=HTTPTransport(urlopen)).fetch(
            provider_code="600000.ss",
            trading_date=date(2025, 1, 2),
        )

    assert error.value.category == "invalid_response"
    assert error.value.problem.status == 502
