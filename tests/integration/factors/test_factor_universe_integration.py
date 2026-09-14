from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from mmqp.adapters.parquet.factors import ParquetFactorResearchRepository
from mmqp.adapters.sqlite.universes import SqliteUniverseMembershipRepository
from mmqp.application.factors import FactorService
from mmqp.application.universes import UniverseService
from mmqp.domain.factors import FactorDefinition, FactorEvaluationRequest, FactorInput
from mmqp.domain.universes import LifecycleVersion, UniverseMembership


def _factor_definition() -> FactorDefinition:
    return FactorDefinition(
        definition_id="price-reversal",
        version_id="v1",
        snapshot_schema_version="schema-v1",
        input_fields=("daily_bar_close",),
        primary_input_field="daily_bar_close",
        observation_window=1,
        transformations=(),
        missing_value_rule="EXCLUDE",
        extreme_value_rule="NONE",
        standardization_rule="ZSCORE",
        neutralization_rule="NONE",
        transformation_specification_version="spec-v1",
    )


def test_membership_and_factor_layers_reconcile() -> None:
    with TemporaryDirectory() as folder:
        root = Path(folder)
        universe = UniverseService(SqliteUniverseMembershipRepository(root / "universe.sqlite"))
        membership = UniverseMembership(
            membership_id="member-asset-a",
            universe_version="universe-v1",
            canonical_asset_id="ASSET-A",
            effective_from=date(2025, 1, 1),
            effective_to=None,
            membership_source="MASTER",
            source_version="master-v1",
        )
        universe.create(membership)
        lifecycle = LifecycleVersion(
            version_id="asset-master-v1",
            canonical_asset_id="ASSET-A",
            effective_from=date(2025, 1, 1),
            effective_to=None,
            lifecycle_status="ACTIVE",
        )
        membership_selection = universe.select(
            [membership],
            "universe-v1",
            date(2025, 1, 2),
            datetime(2025, 1, 2, 12, tzinfo=UTC),
            lifecycles=[lifecycle],
        )
        assert membership_selection.included == ("ASSET-A",)

        factors = FactorService(ParquetFactorResearchRepository(root / "factors"))
        definition = factors.create(_factor_definition())
        result = factors.evaluate(
            FactorEvaluationRequest(
                definition=definition,
                snapshot_id="snapshot-1",
                snapshot_schema_version="schema-v1",
                universe_version="universe-v1",
                factor_date=date(2025, 1, 2),
                decision_at=datetime(2025, 1, 2, 12, tzinfo=UTC),
                inputs=(
                    FactorInput(
                        input_version_id="close-v1",
                        field_name="daily_bar_close",
                        canonical_asset_id="ASSET-A",
                        observation_date=date(2025, 1, 1),
                        value=Decimal("100"),
                        available_at=datetime(2025, 1, 1, 20, tzinfo=UTC),
                    ),
                ),
            ),
        )
        assert result.values[0].value == Decimal("100")
        stored_definition = factors.find(definition.definition_id)
        assert factors.list() == [stored_definition]
