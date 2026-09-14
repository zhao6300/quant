from __future__ import annotations

from mmqp.adapters.data_connectors.base import DailyBarConnector
from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.stooq import StooqDailyBarConnector
from mmqp.adapters.data_connectors.yahoo import YahooFinanceDailyBarConnector

CONNECTED_DAILY_BAR_SOURCES: tuple[str, ...] = ("stooq", "yahoo-finance")


def daily_bar_connectors(transport: HTTPTransport | None = None) -> dict[str, DailyBarConnector]:
    selected = transport if transport is not None else HTTPTransport()
    return {
        "stooq": StooqDailyBarConnector(transport=selected),
        "yahoo-finance": YahooFinanceDailyBarConnector(transport=selected),
    }
