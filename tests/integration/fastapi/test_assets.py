from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mmqp.adapters.fastapi.app import app, get_asset_registry_store
from mmqp.adapters.sqlite.asset_repository import SqliteAssetRegistryRepository


@pytest.fixture()
def asset_database(tmp_path: Path) -> Iterator[Path]:
    database = tmp_path / "assets.sqlite"
    app.dependency_overrides[get_asset_registry_store] = lambda: SqliteAssetRegistryRepository(database)
    try:
        yield database
    finally:
        app.dependency_overrides.pop(get_asset_registry_store, None)


def _asset_payload() -> dict[str, object]:
    return {
        "market": "A_SHARE",
        "asset_type": "EQUITY",
        "exchange": "SSE",
        "local_code": "600000",
        "name": "上海浦东发展银行",
        "trading_currency": "CNY",
        "lifecycle_status": "ACTIVE",
        "effective_from": "2024-01-01",
        "effective_to": None,
    }


def test_asset_registration_and_resolution(asset_database: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/assets", json=_asset_payload())
        assert response.status_code == 201
        asset = response.json()
        repeated = client.post("/api/v1/assets", json=_asset_payload())

        resolved = client.get(f"/api/v1/assets/{asset['asset_id']}", params={"effective_at": "2024-06-01"})
        missing = client.get("/api/v1/assets/missing")

    assert repeated.status_code == 201
    assert repeated.json()["asset_id"] == asset["asset_id"]
    assert resolved.status_code == 200
    assert resolved.json()["identity"]["local_code"] == "600000"
    assert missing.status_code == 404
    assert missing.json()["kind"] == "platform/request-error"


def test_provider_mapping_creation_and_resolution(asset_database: Path) -> None:
    with TestClient(app) as client:
        asset = client.post("/api/v1/assets", json=_asset_payload()).json()
        created = client.post(
            "/api/v1/assets/provider-mappings",
            json={
                "provider": "tushare",
                "provider_code": "600000.SH",
                "asset_id": asset["asset_id"],
                "effective_from": "2024-01-01",
                "effective_to": "2024-12-31",
            },
        )
        repeated = client.post(
            "/api/v1/assets/provider-mappings",
            json={
                "provider": "tushare",
                "provider_code": "600000.SH",
                "asset_id": asset["asset_id"],
                "effective_from": "2024-01-01",
                "effective_to": "2024-12-31",
            },
        )

    assert created.status_code == 201
    assert isinstance(created.json()["mapping_id"], str)
    assert created.json()["mapping_id"] == repeated.json()["mapping_id"]
