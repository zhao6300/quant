from fastapi.testclient import TestClient

from mmqp.adapters.fastapi.app import app

EXPECTED_IDS = {
    "akshare",
    "stooq",
    "yahoo-finance",
    "baostock",
    "tushare",
    "alpha-vantage",
    "financial-modeling-prep",
    "finnhub",
    "tiingo",
    "polygon-io",
    "sec-edgar",
    "hkex-news",
    "fred",
    "ecb",
    "exchange-calendars",
    "pandas-market-calendars",
    "iex-cloud",
    "twelve-data",
    "nasdaq-data-link",
}


def test_data_sources_endpoint_returns_the_catalog() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/data-sources")

    assert response.status_code == 200
    payload = response.json()
    assert {source["id"] for source in payload} == EXPECTED_IDS
    assert {source["provider"] for source in payload} == {
        "akshare",
        "stooq",
        "yfinance",
        "baostock",
        "tushare",
        "alphavantage",
        "financialmodelingprep",
        "finnhub",
        "tiingo",
        "polygon",
        "sec-edgar",
        "hkex",
        "fred",
        "ecb",
        "exchange_calendars",
        "pandas_market_calendars",
        "iexcloud",
        "twelvedata",
        "nasdaq-data-link",
    }
    assert {
        source["id"]: source["implementation_status"]
        for source in payload
        if source["implementation_status"] == "connected"
    } == {"stooq": "connected", "yahoo-finance": "connected"}
    assert {
        source["id"]: source["source_id"]
        for source in payload
        if source["id"] in {"stooq", "yahoo-finance"}
    } == {"stooq": "stooq", "yahoo-finance": "yahoo-finance"}
