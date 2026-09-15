from __future__ import annotations

import json
import pytest
from datetime import date
from decimal import Decimal

from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.yahoo import YahooFinanceDailyBarConnector
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


def test_yahoo_connector_normalizes_the_chart_daily_quote() -> None:
    class _FakeResponseSource:
        def __init__(self, encoded: bytes) -> None:
            self._encoded = encoded

        def read(self) -> bytes:
            return self._encoded

    payload = json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "meta": {"currency": "USD"},
                        "timestamp": ["2025-01-02"],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [236.11],
                                    "high": [236.11],
                                    "low": [225.31],
                                    "close": [225.91],
                                    "volume": [52723500],
                                }
                            ]
                        },
                    }
                ]
            }
        }
    ).encode("utf-8")

    class _FakeTransport(HTTPTransport):
        def json(self, url: str) -> dict[str, object]:
            return json.loads(payload.decode("utf-8"))

    observation = YahooFinanceDailyBarConnector(transport=_FakeTransport()).fetch(
        provider_code="AAPL",
        trading_date=date(2025, 1, 2),
    )
    assert observation.open == Decimal("236.11")
    assert observation.high == Decimal("236.11")
    assert observation.low == Decimal("225.31")
    assert observation.close == Decimal("225.91")
    assert observation.volume == Decimal("52723500")
    assert observation.provider == "yfinance"
    assert observation.trading_date == date(2025, 1, 2)
    assert observation.trading_currency == "USD"


def test_yahoo_connector_falls_back_to_the_latest_completed_bar() -> None:
    timestamps = ["2025-01-02"]
    quote_values = {
        "open": [236.11],
        "high": [236.11],
        "low": [225.31],
        "close": [225.91],
        "volume": [52723500],
    }
    response = {
        "chart": {
            "result": [
                {
                    "meta": {"currency": "CNY"},
                    "timestamp": timestamps,
                    "indicators": {"quote": [quote_values]},
                }
            ]
        }
    }

    class _FakeTransport(HTTPTransport):
        def json(self, url: str) -> dict[str, object]:
            return response

    observation = YahooFinanceDailyBarConnector(transport=_FakeTransport()).fetch(
        provider_code="600000.SS",
        trading_date=date(2025, 1, 3),
    )
    assert observation.trading_date == date(2025, 1, 2)
    assert observation.close == Decimal("225.91")
    assert observation.trading_currency == "CNY"
    assert observation.provider_code == "600000.SS"
    assert observation.as_of.year >= 2025


def test_yahoo_connector_rejects_a_day_without_any_completed_bar() -> None:
    timestamps = ["2025-01-02"]
    response = {
        "chart": {
            "result": [
                {
                    "meta": {"currency": "CNY"},
                    "timestamp": timestamps,
                    "indicators": {"quote": [{"open": [None], "high": [None], "low": [None], "close": [None], "volume": [None]}]},
                }
            ]
        }
    }

    class _FakeTransport(HTTPTransport):
        def json(self, url: str) -> dict[str, object]:
            return response

    with pytest.raises(ProviderCategorizedError) as error:
        YahooFinanceDailyBarConnector(transport=_FakeTransport()).fetch(
            provider_code="600000.SS",
            trading_date=date(2025, 1, 1),
        )
    assert error.value.category == "invalid_response"
    assert error.value.problem.status == 502
