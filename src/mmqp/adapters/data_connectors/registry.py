from __future__ import annotations

from mmqp.adapters.data_connectors.base import DailyBarConnector, FundamentalFactConnector
from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.sec_edgar import SECEDGARConnector
from mmqp.adapters.data_connectors.stooq import StooqDailyBarConnector
from mmqp.adapters.data_connectors.yahoo import YahooFinanceDailyBarConnector

CONNECTED_DAILY_BAR_SOURCES: tuple[str, ...] = ("stooq", "yahoo-finance")
CONNECTED_FUNDAMENTAL_FACT_SOURCES: tuple[str, ...] = ("sec-edgar",)


def daily_bar_connectors(transport: HTTPTransport | None = None) -> dict[str, DailyBarConnector]:
    selected = transport if transport is not None else HTTPTransport()
    return {
        "stooq": StooqDailyBarConnector(transport=selected),
        "yahoo-finance": YahooFinanceDailyBarConnector(transport=selected),
    }


def fundamental_fact_connectors(transport: HTTPTransport | None = None) -> dict[str, FundamentalFactConnector]:
    selected = transport if transport is not None else HTTPTransport()
    return {
        "sec-edgar": SECEDGARConnector(transport=selected),
    }
