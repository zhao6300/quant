from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from mmqp.adapters.fastapi.app import app, get_source_ingestion_service
from mmqp.domain.ingestion import DailyBar

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
        assert usage["method"] == ("GET" if source["category"] == "market" else "POST")
        assert usage["endpoint"].startswith(f"/api/v1/data-sources/{source_id}/")
        assert usage["request_fields"]
        assert all(field["required"] for field in usage["request_fields"])
        if source["requires_auth"]:
            assert usage["required_env"]


def test_source_quote_endpoint_exposes_daily_bar_fields() -> None:
    @dataclass(frozen=True)
    class _FakePreview:
        source_id: str
        market: str
        exchange: str
        canonical_asset_id: str
        provider_code: str
        observation: DailyBar

    class _FakeService:
        def preview(self, command):
            assert command.source_id == "stooq"
            assert command.provider_code == "AAPL"
            assert command.trading_date == date(2026, 9, 14)
            return _FakePreview(
                source_id=command.source_id,
                market=command.market,
                exchange=command.exchange,
                canonical_asset_id=command.canonical_asset_id,
                provider_code=command.provider_code,
                observation=DailyBar(
                    canonical_asset_id=command.canonical_asset_id,
                    provider_code=command.provider_code,
                    trading_date=command.trading_date,
                    open=Decimal("100"),
                    high=Decimal("101"),
                    low=Decimal("99"),
                    close=Decimal("100.5"),
                    volume=Decimal("1000"),
                    turnover=Decimal("100500"),
                    trading_currency="CNY",
                    provider_available_at=datetime(2026, 9, 14, tzinfo=UTC),
                    retrieved_at=datetime(2026, 9, 14, tzinfo=UTC),
                    provider="stooq",
                    provenance_id="prov-1",
                ),
            )

    app.dependency_overrides[get_source_ingestion_service] = lambda: _FakeService()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/data-sources/stooq/quote"
                "?market=A_SHARE&exchange=SSE&symbol=AAPL&trading_date=2026-09-14"
            )
    finally:
        app.dependency_overrides.pop(get_source_ingestion_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_id"] == "stooq"
    assert payload["provider_code"] == "AAPL"
    assert payload["market"] == "A_SHARE"
    assert payload["exchange"] == "SSE"
    assert set(payload) >= {
        "trading_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover",
        "trading_currency",
    }


def test_source_history_endpoint_exposes_multiple_daily_bars() -> None:
    @dataclass(frozen=True)
    class _FakeHistoryPreview:
        source_id: str
        market: str
        exchange: str
        canonical_asset_id: str
        provider_code: str
        observations: tuple[DailyBar, ...]

    class _FakeHistoryService:
        def history(self, command):
            assert command.source_id == "stooq"
            assert command.provider_code == "AAPL"
            assert command.limit == 2
            return _FakeHistoryPreview(
                source_id=command.source_id,
                market=command.market,
                exchange=command.exchange,
                canonical_asset_id=command.canonical_asset_id,
                provider_code=command.provider_code,
                observations=(
                    DailyBar(
                        canonical_asset_id=command.canonical_asset_id,
                        provider_code=command.provider_code,
                        trading_date=command.start_date,
                        open=Decimal("100"),
                        high=Decimal("101"),
                        low=Decimal("99"),
                        close=Decimal("100.5"),
                        volume=Decimal("1000"),
                        turnover=Decimal("100500"),
                        trading_currency="CNY",
                        provider_available_at=datetime(2026, 9, 14, tzinfo=UTC),
                        retrieved_at=datetime(2026, 9, 14, tzinfo=UTC),
                        provider="stooq",
                        provenance_id="prov-1",
                    ),
                    DailyBar(
                        canonical_asset_id=command.canonical_asset_id,
                        provider_code=command.provider_code,
                        trading_date=command.end_date,
                        open=Decimal("101"),
                        high=Decimal("102"),
                        low=Decimal("100"),
                        close=Decimal("101.5"),
                        volume=Decimal("1200"),
                        turnover=Decimal("120000"),
                        trading_currency="CNY",
                        provider_available_at=datetime(2026, 9, 15, tzinfo=UTC),
                        retrieved_at=datetime(2026, 9, 15, tzinfo=UTC),
                        provider="stooq",
                        provenance_id="prov-2",
                    ),
                ),
            )

    app.dependency_overrides[get_source_ingestion_service] = (lambda: _FakeHistoryService())
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/data-sources/stooq/history"
                "?market=A_SHARE&exchange=SSE&symbol=AAPL&trading_date=2026-09-14&limit=2"
            )
    finally:
        app.dependency_overrides.pop(get_source_ingestion_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["bars"]) == 2
