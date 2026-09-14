from __future__ import annotations

import os
import tempfile
from datetime import UTC, date, datetime
from decimal import Decimal

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
        provider_available_at=datetime(2020, 1, 1, 12, tzinfo=UTC)
        if revision_version == "r1"
        else datetime(2020, 1, 2, 12, tzinfo=UTC),
        provider="P",
        revision_version=revision_version,
        provenance_id="P",
    )


@settings(max_examples=16, deadline=None)
@given(value=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000")))
def test_fact_selection_uses_latest_available_at(value: Decimal) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repository = SqliteDataVersionRepository(os.path.join(directory, "facts.sqlite3"))
        repository.publish(_fact("r1", value))
        repository.publish(_fact("r2", value))
        selected = repository.select_fact(
            "ASSET",
            "Revenue",
            date(2020, 1, 1),
            date(2020, 3, 31),
            datetime(2020, 1, 2, 23, tzinfo=UTC),
        )

        assert selected is not None
        assert selected.observation is not None
        assert selected.observation.revision_version == "r2"
        assert selected.observation.value == value
