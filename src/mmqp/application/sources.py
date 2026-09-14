from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SourceCategory = Literal["market", "fundamental", "corporate_action", "macro", "calendar"]
SourceScope = Literal["A_SHARE", "HONG_KONG", "UNITED_STATES", "GLOBAL"]
SourceFrequency = Literal["daily", "event", "reference", "monthly", "quarterly"]
ImplementationStatus = Literal["cataloged", "connected"]


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceRequestField:
    name: str
    label: str
    value_type: Literal["string", "integer", "date"]
    required: bool
    description: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceUsageDefinition:
    endpoint: str
    method: Literal["POST"]
    request_fields: tuple[SourceRequestField, ...]
    required_env: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class DataSourceDefinition:
    id: str
    provider: str
    display_name: str
    category: SourceCategory
    scope: SourceScope
    frequency: SourceFrequency
    source_id: str | None = None
    implementation_status: ImplementationStatus = "connected"
    requires_auth: bool
    documentation_url: str
    note: str = ""


def source_usage(source: DataSourceDefinition) -> SourceUsageDefinition:
    required_env = _required_env(source.id)
    if source.category == "market":
        return SourceUsageDefinition(
            endpoint=f"/api/v1/data-sources/{source.id}/daily-bars",
            method="POST",
            request_fields=(
                SourceRequestField(
                    name="canonical_asset_id",
                    label="Canonical Asset ID",
                    value_type="string",
                    required=True,
                    description="Canonical stable identity used inside the platform.",
                ),
                SourceRequestField(
                    name="provider_code",
                    label="Provider Code",
                    value_type="string",
                    required=True,
                    description="The ticker/code accepted by the connected provider.",
                ),
                SourceRequestField(
                    name="trading_date",
                    label="Trading Date",
                    value_type="date",
                    required=True,
                    description="The trading day being fetched/ingested.",
                ),
            ),
            required_env=required_env,
        )
    if source.category == "macro":
        return SourceUsageDefinition(
            endpoint=f"/api/v1/data-sources/{source.id}/facts",
            method="POST",
            request_fields=(
                SourceRequestField(
                    name="canonical_asset_id",
                    label="Series ID",
                    value_type="string",
                    required=True,
                    description="Provider-specific canonical/series reference.",
                ),
                SourceRequestField(
                    name="metric_code",
                    label="Metric Code",
                    value_type="string",
                    required=True,
                    description="Provider-specific metric/series identifier.",
                ),
            ),
            required_env=required_env,
        )
    if source.category == "fundamental":
        return SourceUsageDefinition(
            endpoint=f"/api/v1/data-sources/{source.id}/facts",
            method="POST",
            request_fields=(
                SourceRequestField(
                    name="canonical_asset_id",
                    label="Canonical Asset ID",
                    value_type="string",
                    required=True,
                    description="Canonical stable identity used inside the platform.",
                ),
                SourceRequestField(
                    name="provider_code",
                    label="Provider Code",
                    value_type="string",
                    required=True,
                    description="The issuer/ticker accepted by the connected provider.",
                ),
                SourceRequestField(
                    name="metric_code",
                    label="Metric Code",
                    value_type="string",
                    required=True,
                    description="Provider-specific financial metric identifier.",
                ),
            ),
            required_env=required_env,
        )
    if source.category == "corporate_action":
        return SourceUsageDefinition(
            endpoint=f"/api/v1/data-sources/{source.id}/corporate-actions",
            method="POST",
            request_fields=(
                SourceRequestField(
                    name="canonical_asset_id",
                    label="Canonical Asset ID",
                    value_type="string",
                    required=True,
                    description="Canonical stable identity used inside the platform.",
                ),
                SourceRequestField(
                    name="provider_code",
                    label="Provider Code",
                    value_type="string",
                    required=True,
                    description="The listed code accepted by the source.",
                ),
                SourceRequestField(
                    name="posting_date",
                    label="Posting Date",
                    value_type="date",
                    required=True,
                    description="The disclosure/announcement date.",
                ),
            ),
        )
    return SourceUsageDefinition(
        endpoint=f"/api/v1/data-sources/{source.id}/calendar",
        method="POST",
        request_fields=(
            SourceRequestField(
                name="calendar_code",
                label="Calendar Code",
                value_type="string",
                required=True,
                description="The provider-specific calendar identifier.",
            ),
            SourceRequestField(
                name="start_date",
                label="Start Date",
                value_type="date",
                required=True,
                description="Inclusive window start.",
            ),
            SourceRequestField(
                name="end_date",
                label="End Date",
                value_type="date",
                required=True,
                description="Inclusive window end.",
            ),
        ),
    )


def source_usage_payload(source: DataSourceDefinition) -> dict[str, Any]:
    usage = source_usage(source)
    return {
        "endpoint": usage.endpoint,
        "method": usage.method,
        "request_fields": [
            {
                "name": field.name,
                "label": field.label,
                "value_type": field.value_type,
                "required": field.required,
                "description": field.description,
            }
            for field in usage.request_fields
        ],
        "required_env": usage.required_env,
    }


def _required_env(source_id: str) -> tuple[str, ...]:
    mapping = {
        "tushare": ("TUSHARE_API_TOKEN",),
        "alpha-vantage": ("ALPHA_VANTAGE_API_KEY",),
        "financial-modeling-prep": ("FINANCIAL_MODELING_PREP_API_KEY",),
        "finnhub": ("FINNHUB_API_KEY",),
        "tiingo": ("TIINGO_API_KEY",),
        "polygon-io": ("POLYGON_API_KEY",),
        "sec-edgar": (),
        "fred": ("FRED_API_KEY",),
        "iex-cloud": ("IEX_CLOUD_API_TOKEN",),
        "twelve-data": ("TWELVE_DATA_API_KEY",),
        "nasdaq-data-link": ("NASDAQ_DATA_LINK_API_KEY",),
    }
    return mapping.get(source_id, ())


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
        source_id="stooq",
        implementation_status="connected",
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
        source_id="yahoo-finance",
        implementation_status="connected",
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
        source_id="sec-edgar",
        implementation_status="connected",
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
