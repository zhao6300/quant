from __future__ import annotations

from importlib import import_module

from mmqp.adapters.data_connectors.base import DailyBarConnector, FundamentalFactConnector
from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.http_sources import rest_daily_bar_connectors
from mmqp.adapters.data_connectors.package_sources import (
    AkShareDailyBarConnector,
    BaoStockDailyBarConnector,
)
from mmqp.adapters.data_connectors.sec_edgar import SECEDGARConnector
from mmqp.adapters.data_connectors.source_connectors import FREDObservationsConnector
from mmqp.adapters.data_connectors.stooq import StooqDailyBarConnector
from mmqp.adapters.data_connectors.yahoo import YahooFinanceDailyBarConnector

CONNECTED_DAILY_BAR_SOURCES: tuple[str, ...] = (
    "stooq",
    "yahoo-finance",
    "akshare",
    "baostock",
    "tushare",
    "alpha-vantage",
    "financial-modeling-prep",
    "finnhub",
    "tiingo",
    "polygon-io",
    "iex-cloud",
    "twelve-data",
    "nasdaq-data-link",
    "ecb",
)
CONNECTED_FUNDAMENTAL_FACT_SOURCES: tuple[str, ...] = ("sec-edgar", "fred")


def daily_bar_endpoint_connectors(transport: HTTPTransport | None = None) -> dict[str, DailyBarConnector]:
    selected = transport if transport is not None else HTTPTransport()
    connectors: dict[str, DailyBarConnector] = dict(rest_daily_bar_connectors(selected))
    connectors.update(
        {
            "stooq": StooqDailyBarConnector(transport=selected),
            "yahoo-finance": YahooFinanceDailyBarConnector(transport=selected),
        }
    )
    return connectors


def daily_bar_connectors(
    transport: HTTPTransport | None = None,
    akshare: object | None = None,
    baostock: object | None = None,
) -> dict[str, DailyBarConnector]:
    connectors = daily_bar_endpoint_connectors(transport)
    if akshare is None:
        try:
            akshare = import_module("akshare")
        except ImportError:
            akshare = None
    if akshare is not None:
        connectors[AkShareDailyBarConnector(akshare).provider] = AkShareDailyBarConnector(akshare)
    if baostock is None:
        try:
            baostock = import_module("baostock")
        except ImportError:
            baostock = None
    if baostock is not None:
        connectors[BaoStockDailyBarConnector(baostock).provider] = BaoStockDailyBarConnector(baostock)
    return connectors


def fundamental_fact_connectors(
    transport: HTTPTransport | None = None,
    fred_api_key: str = "",
) -> dict[str, FundamentalFactConnector]:
    selected = transport if transport is not None else HTTPTransport()
    return {
        "sec-edgar": SECEDGARConnector(transport=selected),
        "fred": FREDObservationsConnector(transport=selected, api_key=fred_api_key),
    }
