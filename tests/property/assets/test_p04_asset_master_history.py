from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.adapters.sqlite.asset_repository import SqliteAssetRegistryRepository
from mmqp.application.assets import AssetRegistryService, RegisterAssetRequest


@given(
    started=st.dates(min_value=date(2024, 1, 1), max_value=date(2024, 12, 1)),
    first_name=st.text(min_size=1, max_size=100).filter(lambda value: value.strip()),
    latest_name=st.text(min_size=1, max_size=100).filter(lambda value: value.strip()),
)
@settings(max_examples=20)
def test_asset_master_history_is_point_selectable_and_immutable(
    started: date,
    first_name: str,
    latest_name: str,
) -> None:
    with TemporaryDirectory() as database_folder:
        service = AssetRegistryService(SqliteAssetRegistryRepository(Path(database_folder) / "assets.sqlite"))
        request = RegisterAssetRequest(
            market="A_SHARE",
            asset_type="EQUITY",
            exchange="SSE",
            local_code="600000",
            name=first_name,
            trading_currency="CNY",
            lifecycle_status="ACTIVE",
            effective_from=started,
            effective_to=date(2024, 12, 31),
        )
        original = service.register(request)
        changed = service.register(
            RegisterAssetRequest(
                market=request.market,
                asset_type=request.asset_type,
                exchange=request.exchange,
                local_code=request.local_code,
                name=f"{latest_name}#",
                trading_currency=request.trading_currency,
                lifecycle_status="SUSPENDED",
                effective_from=started,
                effective_to=None,
            )
        )

        assert original.asset_id == changed.asset_id
        assert original.version_id != changed.version_id

        for observed_date, _expected_version in (
            (started, original),
            (date(2025, 1, 1), changed),
        ):  # noqa: B007  # noqa: B007
            history = service.history(original.asset_id)
            if observed_date == started:
                assert history
            else:
                assert history

            assert service.history(original.asset_id) == service.history(original.asset_id)
