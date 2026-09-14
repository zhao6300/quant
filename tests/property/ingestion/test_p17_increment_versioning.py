from __future__ import annotations

import tempfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.adapters.sqlite.data_versions import SqliteDataVersionRepository
from mmqp.domain.ingestion import FundamentalFact


def _fact(revision_version: str, value: Decimal) -> FundamentalFact:
    return FundamentalFact(
        canonical_asset_id="ASSET",
        metric_name="Revenue",
        value=value,
        unit="USD",
        currency="USD",
        reporting_period_start=date(2020, 1, 1),
        reporting_period_end=date(2020, 3, 31),
        announcement_at=datetime(2020, 1, 1, tzinfo=UTC),
        provider_available_at=datetime(2020, 1, 2, 12, tzinfo=UTC),
        provider="P",
        revision_version=revision_version,
        provenance_id="P",
    )


@settings(max_examples=16, deadline=None)
@given(value=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000")))
def test_increment_planning_and_observation_versioning_are_canonical(value: Decimal) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repository = SqliteDataVersionRepository(str(Path(directory) / "facts.sqlite3"))
        original = repository.publish(_fact("r1", value))
        successor = repository.publish(_fact("r2", value))

        assert successor.revision_position == original.revision_position + 1
        assert successor.predecessor_id == original.version_id
        assert [
            version.version_id
            for version in repository.fact_history("ASSET", "Revenue", date(2020, 1, 1), date(2020, 3, 31))
        ] == [original.version_id, successor.version_id]
