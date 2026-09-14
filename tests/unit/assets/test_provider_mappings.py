from datetime import date

import pytest

from mmqp.adapters.sqlite.asset_repository import SqliteAssetRegistryRepository
from mmqp.application.assets import AssetRegistryService, RegisterAssetRequest
from mmqp.domain.assets import AssetRecordValidationError

ASSET_PAYLOAD = {
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


@pytest.fixture()
def service(tmp_path) -> AssetRegistryService:
    service = AssetRegistryService(SqliteAssetRegistryRepository(tmp_path / "assets.sqlite"))
    service.register(RegisterAssetRequest(**ASSET_PAYLOAD))
    return service


def register_mapping(service: AssetRegistryService, provider_code: str = "600000.SH"):
    asset = service.register(RegisterAssetRequest(**ASSET_PAYLOAD))
    return service.build_provider_mapping(
        provider="tushare",
        provider_code=provider_code,
        asset_id=asset.asset_id,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 12, 31),
    )


def test_provider_mapping_resolution_has_three_outcomes(service: AssetRegistryService):
    mapping = register_mapping(service)

    resolved = service.resolve_provider_mapping(
        provider="tushare", provider_code="600000.SH", observation_date=date(2024, 6, 1)
    )
    unresolved = service.resolve_provider_mapping(
        provider="tushare", provider_code="600000.SH", observation_date=date(2025, 6, 1)
    )
    none_match = service.resolve_provider_mapping(
        provider="tushare", provider_code="missing", observation_date=date(2024, 6, 1)
    )
    duplicate = register_mapping(service)

    assert resolved.status == "resolved"
    assert resolved.asset_id == mapping.asset_id
    assert len(resolved.matches) == 1
    assert unresolved.status == "unresolved"
    assert unresolved.matches == ()
    assert none_match.status == "unresolved"
    assert duplicate.id == mapping.id


def test_provider_mapping_ambiguous_resolution_returns_all_matches(service: AssetRegistryService):
    first = register_mapping(service)
    second_asset = service.register(
        RegisterAssetRequest(**(ASSET_PAYLOAD | {"local_code": "600001", "name": "浦发银行（对照）"}))
    )
    second = service.build_provider_mapping(
        provider="tushare",
        provider_code="600000.SH",
        asset_id=second_asset.asset_id,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 12, 31),
    )

    ambiguous = service.resolve_provider_mapping(
        provider="tushare", provider_code="600000.SH", observation_date=date(2024, 6, 1)
    )

    assert ambiguous.status == "ambiguous"
    assert ambiguous.asset_id is None
    assert ambiguous.matches == (first, second)


def test_invalid_provider_mapping_reports_all_errors_and_preserves_state(service: AssetRegistryService):
    mapping = register_mapping(service)

    with pytest.raises(AssetRecordValidationError) as captured:
        service.build_provider_mapping(
            provider="",
            provider_code="x" * 129,
            asset_id="missing",
            effective_from=date(2024, 2, 1),
            effective_to=date(2024, 1, 1),
        )

    assert captured.value.fields == ["provider", "provider_code", "asset_id", "effective_to"]
    assert service.resolve_provider_mapping(
        provider="tushare", provider_code=mapping.provider_code, observation_date=date(2024, 6, 1)
    ).matches == (mapping,)
