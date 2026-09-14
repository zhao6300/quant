from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SourceCategory = Literal["market", "fundamental", "corporate_action", "macro", "calendar"]
SourceScope = Literal["A_SHARE", "HONG_KONG", "UNITED_STATES", "GLOBAL"]
SourceFrequency = Literal["daily", "event", "reference", "monthly", "quarterly"]
ImplementationStatus = Literal["cataloged", "connected"]


@dataclass(frozen=True, slots=True, kw_only=True)
class DataSourceDefinition:
    id: str
    provider: str
    display_name: str
    category: SourceCategory
    scope: SourceScope
    frequency: SourceFrequency
    implementation_status: ImplementationStatus = "cataloged"
    requires_auth: bool
    documentation_url: str
    note: str = ""


DATA_SOURCES: tuple[DataSourceDefinition, ...] = (
    DataSourceDefinition(
        id="akshare",
        provider="akshare",
        display_name="AkShare",
        category="market",
        scope="GLOBAL",
        frequency="daily",
        requires_auth=False,
        documentation_url="https://github.com/akfamily/akshare",
        note="覆盖 A股、港股、美股、指数、基金和常用日历。",
    ),
    DataSourceDefinition(
        id="stooq",
        provider="stooq",
        display_name="Stooq",
        category="market",
        scope="GLOBAL",
        frequency="daily",
        requires_auth=False,
        documentation_url="https://stooq.com/q/d/",
        note="无需 API key 的历史日线 CSV。",
    ),
    DataSourceDefinition(
        id="yahoo-finance",
        provider="yfinance",
        display_name="Yahoo Finance",
        category="market",
        scope="GLOBAL",
        frequency="daily",
        requires_auth=False,
        documentation_url="https://pypi.org/project/yfinance/",
        note="涵盖美股、港股、A股日线与基础公司信息。",
    ),
    DataSourceDefinition(
        id="baostock",
        provider="baostock",
        display_name="BaoStock",
        category="market",
        scope="A_SHARE",
        frequency="daily",
        requires_auth=False,
        documentation_url="https://baostock.com",
        note="A股日线、指数与基本面。",
    ),
    DataSourceDefinition(
        id="tushare",
        provider="tushare",
        display_name="Tushare",
        category="market",
        scope="A_SHARE",
        frequency="daily",
        requires_auth=True,
        documentation_url="https://tushare.pro",
        note="免费 token 与额度内可取日线、指数和宏观数据。",
    ),
    DataSourceDefinition(
        id="alpha-vantage",
        provider="alphavantage",
        display_name="Alpha Vantage",
        category="market",
        scope="UNITED_STATES",
        frequency="daily",
        requires_auth=True,
        documentation_url="https://www.alphavantage.co/documentation/",
        note="免费额度取日线、FX 和基本面。",
    ),
    DataSourceDefinition(
        id="financial-modeling-prep",
        provider="financialmodelingprep",
        display_name="Financial Modeling Prep",
        category="fundamental",
        scope="UNITED_STATES",
        frequency="event",
        requires_auth=True,
        documentation_url="https://site.financialmodelingprep.com/developer/docs",
        note="免费额度覆盖财务报表与公司行动。",
    ),
    DataSourceDefinition(
        id="finnhub",
        provider="finnhub",
        display_name="Finnhub",
        category="fundamental",
        scope="GLOBAL",
        frequency="event",
        requires_auth=True,
        documentation_url="https://docs.official-finnhub.com",
        note="免费额度内可取行情、财务与公告。",
    ),
    DataSourceDefinition(
        id="tiingo",
        provider="tiingo",
        display_name="Tiingo",
        category="market",
        scope="UNITED_STATES",
        frequency="daily",
        requires_auth=True,
        documentation_url="https://www.tiingo.com/about/pricing",
        note="免费额度支持美股和 ETF 日线。",
    ),
    DataSourceDefinition(
        id="polygon-io",
        provider="polygon",
        display_name="Polygon.io",
        category="market",
        scope="UNITED_STATES",
        frequency="daily",
        requires_auth=True,
        documentation_url="https://polygon.io/docs",
        note="免费额度可取历史行情和公司行动。",
    ),
    DataSourceDefinition(
        id="sec-edgar",
        provider="sec-edgar",
        display_name="SEC EDGAR",
        category="fundamental",
        scope="UNITED_STATES",
        frequency="event",
        requires_auth=False,
        documentation_url="https://www.sec.gov/edgar",
        note="美股公开公告和财务披露，官方数据源。",
    ),
    DataSourceDefinition(
        id="hkex-news",
        provider="hkex",
        display_name="HKEX News",
        category="corporate_action",
        scope="HONG_KONG",
        frequency="event",
        requires_auth=False,
        documentation_url="https://www.hkexnews.hk",
        note="港股公告与公司行动披露。",
    ),
    DataSourceDefinition(
        id="fred",
        provider="fred",
        display_name="FRED",
        category="macro",
        scope="GLOBAL",
        frequency="monthly",
        requires_auth=True,
        documentation_url="https://fred.stlouisfed.org",
        note="宏观、利率、通胀、汇率和就业序列。",
    ),
    DataSourceDefinition(
        id="ecb",
        provider="ecb",
        display_name="European Central Bank",
        category="macro",
        scope="GLOBAL",
        frequency="daily",
        requires_auth=False,
        documentation_url="https://www.ecb.europa.eu/stats",
        note="官方汇率和 eurozone 宏观数据。",
    ),
    DataSourceDefinition(
        id="exchange-calendars",
        provider="exchange_calendars",
        display_name="Exchange Calendars",
        category="calendar",
        scope="GLOBAL",
        frequency="reference",
        requires_auth=False,
        documentation_url="https://github.com/gerrymanoim/exchange_calendars",
        note="美股、港股、A股交易日历参考。",
    ),
    DataSourceDefinition(
        id="pandas-market-calendars",
        provider="pandas_market_calendars",
        display_name="pandas-market-calendars",
        category="calendar",
        scope="GLOBAL",
        frequency="reference",
        requires_auth=False,
        documentation_url="https://github.com/rsheftel/pandas_market_calendars",
        note="多市场日历参考，适合作为基础节假日源。",
    ),
    DataSourceDefinition(
        id="iex-cloud",
        provider="iexcloud",
        display_name="IEX Cloud",
        category="market",
        scope="UNITED_STATES",
        frequency="daily",
        requires_auth=True,
        documentation_url="https://iexcloud.io",
        note="免费额度支持美股行情和公司信息。",
    ),
    DataSourceDefinition(
        id="twelve-data",
        provider="twelvedata",
        display_name="Twelve Data",
        category="market",
        scope="GLOBAL",
        frequency="daily",
        requires_auth=True,
        documentation_url="https://twelvedata.com/docs",
        note="免费额度覆盖全球轻量行情。",
    ),
    DataSourceDefinition(
        id="nasdaq-data-link",
        provider="nasdaq-data-link",
        display_name="Nasdaq Data Link",
        category="market",
        scope="GLOBAL",
        frequency="daily",
        requires_auth=True,
        documentation_url="https://docs.data.nasdaq.com",
        note="免费额度内可取行情和宏观数据。",
    ),
)


def list_data_sources() -> tuple[DataSourceDefinition, ...]:
    return DATA_SOURCES
