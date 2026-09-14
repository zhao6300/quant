from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mmqp.adapters.fastapi.app import app, get_query_source
from mmqp.adapters.sqlite.data_versions import SqliteDataVersionRepository
from mmqp.adapters.sqlite.query_source import SqliteQuerySource
from mmqp.application.calendars import MARKET_TIMEZONES
from mmqp.domain.calendars import TradingCalendarDay, TradingCalendarVersion, ValuationCalendarVersion
from mmqp.domain.corporate_actions import CorporateActionVersion
from mmqp.domain.ingestion import DailyBar
from mmqp.domain.market_rules import MarketRuleProfile


@pytest.fixture()
def source(tmp_path: Path) -> SqliteQuerySource:
    database = str(tmp_path / "platform.sqlite3")
    repository = SqliteDataVersionRepository(database)
    repository.publish(
        DailyBar(
            canonical_asset_id="ASSET_1",
            trading_date=date(2024, 1, 2),
            open=Decimal("10.00"),
            high=Decimal("10.50"),
            low=Decimal("9.80"),
            close=Decimal("10.25"),
            volume=Decimal("1000"),
            turnover=Decimal("10250.00"),
            trading_currency="USD",
            provider_available_at=datetime(2024, 1, 2, 15, 59, tzinfo=UTC),
            retrieved_at=datetime(2024, 1, 2, 16, 1, tzinfo=UTC),
            provider="test-provider",
            provider_code="AMD",
            provenance_id="prov-test",
        )
    )
    source = SqliteQuerySource(database)
    source._trading_calendar_repository.create(
        TradingCalendarVersion(
            version_id="sse-2024",
            market="A_SHARE",
            exchange="SSE",
            timezone=MARKET_TIMEZONES["A_SHARE"],
            effective_from=date(2024, 1, 1),
            effective_to=None,
            days=(
                TradingCalendarDay(
                    market="A_SHARE",
                    exchange="SSE",
                    date=date(2024, 2, 8),
                    kind="full",
                    sessions=(),
                ),
            ),
        )
    )
    source._market_rule_repository.create(
        MarketRuleProfile(
            version_id="sse-equity",
            market="A_SHARE",
            exchange="SSE",
            asset_type="EQUITY",
            effective_from=date(2024, 1, 1),
            effective_to=None,
            trading_lot=100,
            tick_size=Decimal("0.01"),
            price_limit_rule="STATIC_PERCENTAGE_BASE_REFERENCE",
            price_limit_percent=Decimal("0.10"),
            sell_availability_rule="NEXT_OPEN_MARKET_DATE",
            security_settlement_open_dates=1,
            cash_settlement_open_dates=1,
            permitted_session_types=("regular",),
        )
    )
    source._corporate_action_repository.create(
        CorporateActionVersion(
            canonical_asset_id="ASSET_1",
            event_id="ca-event-1",
            action_type="CASH_DIVIDEND",
            announcement_date=date(2024, 1, 2),
            ex_date=date(2024, 1, 3),
            record_date=date(2024, 1, 5),
            effective_date=date(2024, 1, 6),
            terms={"distribution": "1.00", "currency": "USD"},
            provenance_id="prov-holder",
            version_id="ca-v1",
        )
    )
    source._valuation_calendar_repository.create(
        ValuationCalendarVersion(
            version_id="sse-val-2024",
            market="A_SHARE",
            timezone=MARKET_TIMEZONES["A_SHARE"],
            effective_from=date(2024, 1, 1),
            effective_to=None,
        )
    )
    return source


def test_api_query_uses_live_snapshot_and_returns_filtered_rows(
    source: SqliteQuerySource,
) -> None:
    app.dependency_overrides[get_query_source] = lambda: source
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/queries/results",
            json={
                "snapshot_id": "LIVE",
                "dataset": "DAILY_BAR",
                "filters": [{"field": "trading_currency", "values": ["USD"]}],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["snapshot_id"] == "LIVE"
        assert payload["matching_count"] == 1
        assert payload["returned_count"] == 1
        assert payload["applied_filter_count"] == 1
        assert payload["additional_results"] is False
        assert payload["rows"][0]["canonical_asset_id"] == "ASSET_1"
    finally:
        app.dependency_overrides.pop(get_query_source, None)


def test_api_run_dry_run_receipt_disclaimer(
    source: SqliteQuerySource,
) -> None:
    app.dependency_overrides[get_query_source] = lambda: source
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/runs",
            json={
                "snapshot_id": "LIVE",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "base_currency": "USD",
                "factor_definition_version": "factor-v1",
                "universe_version": "universe-v1",
                "portfolio_definition_version": "portfolio-v1",
                "strategy_version": "strategy-v1",
                "transaction_cost_model_version": "cost-v1",
                "risk_model_version": "risk-v1",
            },
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["run_created"] is False
        assert payload["result_kind"] == "research_simulation"
        assert "no brokerage order sent" in payload["disclaimer"]
    finally:
        app.dependency_overrides.pop(get_query_source, None)


@pytest.mark.parametrize(
    "dataset,expected_version_id,expected_currency",
    [
        ("TRADING_CALENDAR", "sse-2024", None),
        ("MARKET_RULE_PROFILE", "sse-equity", None),
        ("VALUATION_CALENDAR", "sse-val-2024", None),
        ("CORPORATE_ACTION", "ca-v1", "USD"),
    ],
)
def test_api_query_returns_control_plane_records(
    source: SqliteQuerySource,
    dataset: str,
    expected_version_id: str,
    expected_currency: str | None,
) -> None:
    app.dependency_overrides[get_query_source] = lambda: source
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/queries/results",
            json={
                "snapshot_id": "LIVE",
                "dataset": dataset,
                "filters": (
                    [{"field": "canonical_asset_id", "values": ["ASSET_1"]}]
                    if dataset == "CORPORATE_ACTION"
                    else [{"field": "market", "values": ["A_SHARE"]}]
                ),
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["matching_count"] == 1
        assert payload["returned_count"] == 1
        assert payload["rows"][0]["version_id"] == expected_version_id
        assert payload["rows"][0]["data_quality_status"] == "VALID"
        assert payload["rows"][0]["currency"] == expected_currency
    finally:
        app.dependency_overrides.pop(get_query_source, None)
