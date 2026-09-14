from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.adapters.sqlite.asset_repository import SqliteAssetRegistryRepository
from mmqp.application.assets import AssetRegistryService, RegisterAssetRequest

PROVIDER_CODES = ["P001", "P002", "P003"]
START_DATES = [date(2024, 1, 1), date(2024, 4, 1), date(2024, 7, 1)]
END_DATES = [date(2024, 6, 30), date(2024, 9, 30), date(2024, 12, 31)]


@given(provider=st.sampled_from(PROVIDER_CODES))
@settings(max_examples=20, deadline=None)
def test_provider_mapping_resolution_has_three_outcomes(provider: str) -> None:
    with TemporaryDirectory() as database_folder:
        service = AssetRegistryService(SqliteAssetRegistryRepository(Path(database_folder) / "assets.sqlite"))
        first_asset = service.register(
            RegisterAssetRequest(
                market="A_SHARE",
                asset_type="EQUITY",
                exchange="SSE",
                local_code="600001",
                name="浦发银行",
                trading_currency="CNY",
                lifecycle_status="ACTIVE",
                effective_from=START_DATES[0],
                effective_to=None,
            )
        )
        second_asset = service.register(
            RegisterAssetRequest(
                market="A_SHARE",
                asset_type="EQUITY",
                exchange="SSE",
                local_code="600002",
                name="对照资产",
                trading_currency="CNY",
                lifecycle_status="ACTIVE",
                effective_from=START_DATES[0],
                effective_to=None,
            )
        )

        first = service.build_provider_mapping(
            provider=provider,
            provider_code="SAME_CODE",
            asset_id=first_asset.asset_id,
            effective_from=START_DATES[0],
            effective_to=END_DATES[0],
        )
        second = service.build_provider_mapping(
            provider=provider,
            provider_code="SAME_CODE",
            asset_id=second_asset.asset_id,
            effective_from=START_DATES[0],
            effective_to=END_DATES[0],
        )
        resolved_mapping = service.build_provider_mapping(
            provider=provider,
            provider_code="UNIQUE_CODE",
            asset_id=first_asset.asset_id,
            effective_from=START_DATES[0],
            effective_to=END_DATES[0],
        )
        duplicate = service.build_provider_mapping(
            provider=provider,
            provider_code="SAME_CODE",
            asset_id=first_asset.asset_id,
            effective_from=START_DATES[0],
            effective_to=END_DATES[0],
        )

        resolved = service.resolve_provider_mapping(
            provider=provider, provider_code="UNIQUE_CODE", observation_date=date(2024, 3, 1)
        )
        ambiguous = service.resolve_provider_mapping(
            provider=provider, provider_code="SAME_CODE", observation_date=date(2024, 3, 1)
        )
        unresolved = service.resolve_provider_mapping(
            provider=provider, provider_code="MISSING", observation_date=date(2024, 3, 1)
        )

        assert resolved.status == "resolved"
        assert resolved.asset_id == resolved_mapping.asset_id
        assert resolved.matches == (resolved_mapping,)
        assert ambiguous.status == "ambiguous"
        assert ambiguous.asset_id is None
        assert set(ambiguous.matches) == {first, second}
        assert len(ambiguous.matches) == 2
        assert unresolved.status == "unresolved"
        assert unresolved.matches == ()
        assert duplicate.id == first.id
