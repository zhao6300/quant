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
    assert {source["id"]: source["implementation_status"] for source in payload} == {
        source_id: "connected" for source_id in EXPECTED_IDS
    }
    assert {
        source["id"]: source["source_id"] for source in payload if source["id"] in {"stooq", "yahoo-finance"}
    } == {"stooq": "stooq", "yahoo-finance": "yahoo-finance"}
    source_by_id = {source["id"]: source for source in payload}
    for source_id, source in source_by_id.items():
        usage = source["usage"]
        assert usage["method"] == "POST"
        assert usage["endpoint"].startswith(f"/api/v1/data-sources/{source_id}/")
        assert usage["request_fields"]
        assert all(field["required"] for field in usage["request_fields"])
        if source["requires_auth"]:
            assert usage["required_env"]
