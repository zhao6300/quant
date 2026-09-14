from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mmqp.adapters.fastapi import app as fastapi_app_module


@pytest.fixture()
def isolated_control_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    database_path = tmp_path / "control.sqlite3"
    monkeypatch.setattr(
        fastapi_app_module,
        "control_database_path",
        database_path,
    )
    yield database_path


def test_fastapi_startup_seeds_market_baselines_once(
    isolated_control_database: Path,
) -> None:
    with TestClient(fastapi_app_module.app) as client:
        with TestClient(fastapi_app_module.app):
            pass

        for market, exchange in (
            ("A_SHARE", "SSE"),
            ("HONG_KONG", "HKEX"),
            ("UNITED_STATES", "NYSE"),
        ):
            trading_response = client.get(
                "/api/v1/calendars/trading",
                params={"market": market, "exchange": exchange, "as_of": "2026-09-14"},
            )
            valuation_response = client.get(
                "/api/v1/calendars/valuation",
                params={"market": market, "as_of": "2026-09-14"},
            )
            rules_response = client.get(
                "/api/v1/market-rules/list",
                params={"market": market, "exchange": exchange, "asset_type": "EQUITY"},
            )

            assert trading_response.status_code == 200, trading_response.text
            assert valuation_response.status_code == 200, valuation_response.text
            assert rules_response.status_code == 200, rules_response.text
            assert rules_response.json()[0]["version_id"].endswith("-equity-baseline")
