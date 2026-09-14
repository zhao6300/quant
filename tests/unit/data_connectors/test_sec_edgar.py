from __future__ import annotations

from datetime import date
from decimal import Decimal

from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.sec_edgar import SECEDGARConnector


class _FakeTransport(HTTPTransport):
    def json(self, url: str) -> dict[str, object]:
        return {
            "cik": 320193,
            "entityName": "Apple Inc.",
            "currencyCode": "USD",
            "units": {
                "USD": [
                    {
                        "start": "2024-03-31",
                        "end": "2024-03-31",
                        "val": 123456,
                    }
                ]
            },
        }


def test_sec_edgar_connector_normalizes_a_us_gaap_metric() -> None:
    fact = SECEDGARConnector(transport=_FakeTransport()).fetch(
        provider_code="0000320193",
        metric_code="Assets",
    )

    assert fact.metric_name == "us-gaap:Assets"
    assert fact.value == Decimal("123456")
    assert fact.period_start == date(2024, 3, 31)
    assert fact.period_end == date(2024, 3, 31)
    assert fact.provider == "sec-edgar"
