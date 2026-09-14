from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mmqp.adapters.fastapi.app import (
    app,
    get_market_rule_repository,
    get_trading_calendar_repository,
    get_valuation_calendar_repository,
)
from mmqp.adapters.sqlite.calendars import SqliteTradingCalendarRepository, SqliteValuationCalendarRepository
from mmqp.adapters.sqlite.market_rules import SqliteMarketRuleRepository


def _profile(version_id: str) -> dict[str, object]:
    return {
        "version_id": version_id,
        "market": "A_SHARE",
        "exchange": "SSE",
        "asset_type": "EQUITY",
        "effective_from": "2024-01-01",
        "trading_lot": 100,
        "tick_size": "0.01",
        "price_limit_rule": "STATIC_PERCENTAGE_BASE_REFERENCE",
        "price_limit_percent": "0.10",
        "sell_availability_rule": "NEXT_OPEN_MARKET_DATE",
        "security_settlement_open_dates": 1,
        "cash_settlement_open_dates": 1,
        "permitted_session_types": ["regular"],
    }


@pytest.fixture
def control_database(tmp_path: Path) -> Iterator[Path]:
    database = tmp_path / "control.sqlite3"
    app.dependency_overrides.clear()
    yield database
    app.dependency_overrides.clear()


def test_calendar_registration_and_resolution(control_database: Path) -> None:
    calendar_repository = SqliteTradingCalendarRepository(control_database)
    valuation_repository = SqliteValuationCalendarRepository(control_database)
    app.dependency_overrides.update(
        {
            get_trading_calendar_repository: lambda: calendar_repository,
            get_valuation_calendar_repository: lambda: valuation_repository,
        }
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/calendars/trading",
            json={
                "version_id": "sse-2024",
                "market": "A_SHARE",
                "exchange": "SSE",
                "timezone": "Asia/Shanghai",
                "effective_from": "2024-01-01",
                "days": [
                    {"market": "A_SHARE", "exchange": "SSE", "date": "2024-02-08", "kind": "full"},
                    {"market": "A_SHARE", "exchange": "SSE", "date": "2024-02-09", "kind": "half"},
                    {"market": "A_SHARE", "exchange": "SSE", "date": "2024-02-10", "kind": "closed"},
                ],
            },
        )
        assert response.status_code == 201
        assert response.json()["version_id"] == "sse-2024"
        resolved = client.get(
            "/api/v1/calendars/trading",
            params={"market": "A_SHARE", "exchange": "SSE", "as_of": "2024-02-09"},
        )
        assert resolved.status_code == 200
        payload = resolved.json()
        assert payload["days"][1]["kind"] == "half"
        assert client.get("/api/v1/status").status_code == 200


def test_calendar_session_validation_rejects_upsert(control_database: Path) -> None:
    app.dependency_overrides.update(
        {
            get_trading_calendar_repository: lambda: SqliteTradingCalendarRepository(control_database),
            get_valuation_calendar_repository: lambda: SqliteValuationCalendarRepository(control_database),
        }
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/calendars/trading",
            json={
                "version_id": "hk-bad",
                "market": "HONG_KONG",
                "exchange": "HKEX",
                "timezone": "Asia/Hong_Kong",
                "effective_from": "2024-01-01",
                "days": [
                    {
                        "market": "HONG_KONG",
                        "exchange": "HKEX",
                        "date": "2024-01-02",
                        "kind": "half",
                        "sessions": [{"start": "13:30", "end": "13:00", "kind": "regular"}],
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert response.json()["kind"] == "calendar/version-invalid"


def test_market_rule_registration_validation_and_immutability(control_database: Path) -> None:
    app.dependency_overrides.update(
        {
            get_market_rule_repository: lambda: SqliteMarketRuleRepository(control_database),
        }
    )
    good = _profile("sse-equity")
    with TestClient(app) as client:
        response = client.post("/api/v1/market-rules", json=good)
        assert response.status_code == 201
        same = client.post("/api/v1/market-rules", json=_profile("sse-equity-duplicate"))
        assert same.status_code == 201
        assert (
            client.post(
                "/api/v1/market-rules",
                json={**good, "version_id": "bad", "trading_lot": 0, "tick_size": "0"},
            ).status_code
            == 400
        )
        repository = SqliteMarketRuleRepository(control_database)
        with pytest.raises(sqlite3.Error):
            with repository._connection() as connection:
                connection.execute(
                    "UPDATE market_rule_profiles SET trading_lot = 0 WHERE version_id = 'sse-equity'"
                )


def test_market_rules_evaluator_exactness_and_missing_profile(control_database: Path) -> None:
    app.dependency_overrides.update(
        {
            get_market_rule_repository: lambda: SqliteMarketRuleRepository(control_database),
            get_trading_calendar_repository: lambda: SqliteTradingCalendarRepository(control_database),
            get_valuation_calendar_repository: lambda: SqliteValuationCalendarRepository(control_database),
        }
    )
    profile = _profile("sse-equity")
    with TestClient(app) as client:
        assert client.post("/api/v1/market-rules", json=profile).status_code == 201
        assert (
            client.post(
                "/api/v1/calendars/trading",
                json={
                    "version_id": "sse-2024",
                    "market": "A_SHARE",
                    "exchange": "SSE",
                    "timezone": "Asia/Shanghai",
                    "effective_from": "2024-01-01",
                    "days": [
                        {
                            "market": "A_SHARE",
                            "exchange": "SSE",
                            "date": "2024-03-01",
                            "kind": "full",
                        },
                        {
                            "market": "A_SHARE",
                            "exchange": "SSE",
                            "date": "2024-03-04",
                            "kind": "full",
                        },
                    ],
                },
            ).status_code
            == 201
        )
        response = client.post(
            "/api/v1/market-rules/evaluate",
            json={
                "market": "A_SHARE",
                "exchange": "SSE",
                "asset_type": "EQUITY",
                "trade_date": "2024-03-01",
                "side": "BUY",
                "requested_quantity": "1005",
                "requested_price": "10.017",
                "reference_price": "10.00",
                "market_data_price_limit_percent": "0.10",
                "sellable_quantity": "0",
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["filled_quantity"] == "1000"
        assert payload["valid_price"] == "10.01"
        assert payload["rule_source_version_id"] == "sse-equity"
        assert payload["sell_available_date"] == "2024-03-04"
        assert payload["security_settlement_date"] == "2024-03-04"
        assert (
            client.post(
                "/api/v1/market-rules/evaluate",
                json={
                    "market": "HONG_KONG",
                    "exchange": "HKEX",
                    "asset_type": "EQUITY",
                    "trade_date": "2024-03-01",
                    "side": "BUY",
                    "requested_quantity": "10",
                    "requested_price": "10",
                    "reference_price": "10",
                    "market_data_price_band_percent": "0.10",
                    "sellable_quantity": "0",
                },
            ).status_code
            == 404
        )
