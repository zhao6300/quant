from datetime import date

import pytest

from mmqp.adapters.sqlite.asset_repository import SqliteAssetRegistryRepository
from mmqp.application.assets import AssetRegistryService, RegisterAssetRequest
from mmqp.domain.assets import (
    AssetRecordValidationError,
)


@pytest.fixture()
def service(tmp_path) -> AssetRegistryService:
    return AssetRegistryService(SqliteAssetRegistryRepository(tmp_path / "assets.sqlite"))


def asset_request(**overrides):
    base = {
        "market": "A_SHARE",
        "asset_type": "EQUITY",
        "exchange": "SH",
        "local_code": "600000",
        "name": "上海浦东发展银行",
        "trading_currency": "CNY",
        "lifecycle_status": "ACTIVE",
        "effective_from": date(2024, 1, 1),
        "effective_to": None,
    }
    return RegisterAssetRequest(**(base | overrides))


def test_stable_identity_is_discriminating(service: AssetRegistryService):
    first = service.register(asset_request())
    repeated = service.register(asset_request())
    changed = service.register(asset_request(local_code="600001"))

    assert first.asset_id == repeated.asset_id
    assert first.asset_id != changed.asset_id
    assert service.history(first.asset_id) == [repeated]


def test_all_validation_errors_are_reported(service: AssetRegistryService):
    with pytest.raises(AssetRecordValidationError) as captured:
        service.register(
            asset_request(
                market="LONDON",
                asset_type="OPTION",
                exchange=" ",
                local_code=" ",
                name=" ",
                trading_currency="cn",
                lifecycle_status="DELETED",
                effective_from=date(2024, 1, 2),
                effective_to=date(2024, 1, 1),
            )
        )

    assert captured.value.fields == [
        "market",
        "asset_type",
        "exchange",
        "local_code",
        "name",
        "trading_currency",
        "lifecycle_status",
        "effective_to",
    ]
    assert service.history("missing") == []


def test_non_iso_currency_is_invalid(service: AssetRegistryService):
    with pytest.raises(AssetRecordValidationError) as captured:
        service.register(asset_request(trading_currency="AAA"))

    assert captured.value.fields == ["trading_currency"]


def test_append_effective_version_and_as_of(service: AssetRegistryService):
    original = service.register(asset_request())
    changed = service.register(
        asset_request(name="浦发银行", lifecycle_status="SUSPENDED", effective_from=date(2025, 1, 1))
    )
    history_after_close = service.history(original.asset_id)

    assert original.asset_id == changed.asset_id
    assert original.version_id != changed.version_id
    assert len(history_after_close) == 2
    assert history_after_close[0].effective_to is None
    assert service.history(original.asset_id) == [history_after_close[0], changed]
