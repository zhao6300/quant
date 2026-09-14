from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from mmqp.adapters.parquet.universes import ParquetUniverseMembershipRepository
from mmqp.adapters.sqlite.universes import SqliteUniverseMembershipRepository
from mmqp.application.universes import (
    UniverseService,
    select_universe,
    select_universe_history,
)
from mmqp.domain.universes import (
    LifecycleVersion,
    LiquidityInput,
    UniverseMembership,
)


def _membership(
    asset_id: str,
    *,
    membership_id: str | None = None,
    effective_from: date = date(2025, 1, 1),
    effective_to: date | None = None,
    source: str = "MASTER",
) -> UniverseMembership:
    return UniverseMembership(
        membership_id=membership_id or f"{asset_id}-{effective_from}",
        universe_version="universe-v1",
        canonical_asset_id=asset_id,
        effective_from=effective_from,
        effective_to=effective_to,
        membership_source=source,
        source_version="source-1",
    )


@pytest.mark.parametrize("adapter_name", ["sqlite", "parquet"])
def test_membership_is_content_addressed_and_immutable(adapter_name: str) -> None:
    membership = _membership("AAA")
    with TemporaryDirectory() as folder:
        root = Path(folder) / adapter_name
        repository = (
            SqliteUniverseMembershipRepository(root / "universe.sqlite")
            if adapter_name == "sqlite"
            else ParquetUniverseMembershipRepository(root / "parquet")
        )
        service = UniverseService(repository)
        stored = service.create(membership)
        assert service.list() == [stored]
        assert service.find(membership.membership_id) == stored
        with pytest.raises(Exception, match="already exists|Universe membership conflict"):
            service.create(stored)
        if adapter_name == "sqlite":
            with sqlite3.connect(root / "universe.sqlite") as connection:
                with pytest.raises(sqlite3.DatabaseError, match="is immutable"):
                    connection.execute("DELETE FROM universe_memberships")


def test_select_requires_one_effective_interval_and_records_ambiguity() -> None:
    first = _membership("AAA", membership_id="first")
    second = _membership("AAA", membership_id="second")
    missing = _membership("BBB", membership_id="missing", effective_from=date(2025, 3, 1))
    result = select_universe([first, second, missing], "universe-v1", date(2025, 1, 1))
    assert result.included == ()
    assert result.exclusion_counts == {"AMBIGUOUS": 1, "MISSING": 1}
    assert result.excluded[0].canonical_asset_id == "AAA"


def test_universe_selection_treats_a_zero_membership_gap_as_missing() -> None:
    membership = _membership("AAA", effective_from=date(2025, 1, 1), effective_to=date(2025, 1, 2))
    result = select_universe([membership], "universe-v1", date(2025, 1, 3))
    assert result.included == ()
    assert result.excluded[0].reason == "MISSING"


def test_lifecycle_and_pit_liquidity_filters_exclude_evidence() -> None:
    membership = _membership("AAA")
    lifecycles = [
        LifecycleVersion(
            version_id="asset-v1",
            canonical_asset_id="AAA",
            effective_from=date(2025, 1, 1),
            effective_to=None,
            lifecycle_status="SUSPENDED",
        )
    ]
    liquidity = [
        LiquidityInput(
            input_version_id="liquidity-v1",
            canonical_asset_id="AAA",
            available_at=datetime(2025, 1, 1, 21, tzinfo=UTC),
            value=None,
        )
    ]
    result = select_universe(
        [membership],
        "universe-v1",
        date(2025, 1, 1),
        decision_at=datetime(2025, 1, 1, 12, tzinfo=UTC),
        lifecycles=lifecycles,
        liquidity=liquidity,
    )
    assert result.included == ()
    assert result.excluded[0].reason == "LIFECYCLE"
    assert result.lookahead_preventions == ()

    active_lifecycles = [
        lifecycles[0].__class__(
            version_id="asset-v2",
            canonical_asset_id="AAA",
            effective_from=date(2025, 1, 1),
            effective_to=None,
            lifecycle_status="ACTIVE",
        )
    ]
    result = select_universe(
        [membership],
        "universe-v1",
        date(2025, 1, 1),
        decision_at=datetime(2025, 1, 1, 12, tzinfo=UTC),
        lifecycles=active_lifecycles,
        liquidity=liquidity,
    )
    assert result.included == ()
    assert result.excluded[0].reason == "LIQUIDITY"
    assert result.exclusion_counts == {"LIQUIDITY": 1}


def test_history_warns_on_contiguous_source_gaps() -> None:
    left = _membership("AAA", effective_from=date(2025, 1, 1), effective_to=date(2025, 1, 10))
    right = _membership("AAA", effective_from=date(2025, 1, 15), effective_to=date(2025, 1, 20))
    result = select_universe_history(
        [left, right],
        "universe-v1",
        [date(2025, 1, 9), date(2025, 1, 10), date(2025, 1, 14), date(2025, 1, 15)],
    )
    assert result.included == ("AAA",)
    assert len(result.survivorship_warnings) == 1
    warning = result.survivorship_warnings[0]
    assert warning.incomplete_from == date(2025, 1, 14)
    assert warning.incomplete_to == date(2025, 1, 14)
    assert warning.missing_sources == ("MASTER",)
