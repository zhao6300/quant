from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mmqp.adapters.parquet.factors import ParquetFactorResearchRepository
from mmqp.application.factors import FactorService, validate_factor_definition
from mmqp.domain.factors import (
    FactorDefinition,
    FactorEvaluationRequest,
    FactorInput,
    FactorTransformation,
)


def _definition(required_fields: tuple[str, ...]) -> FactorDefinition:
    return FactorDefinition(
        definition_id="factor-1",
        version_id="v1",
        snapshot_schema_version="schema-v1",
        input_fields=required_fields,
        primary_input_field=required_fields[0],
        observation_window=1,
        transformations=(),
        missing_value_rule="EXCLUDE",
        extreme_value_rule="WINSORIZE",
        standardization_rule="ZSCORE",
        neutralization_rule="NONE",
        transformation_specification_version="spec-v1",
    )


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    field_count=st.integers(min_value=1, max_value=4),
    transformation_count=st.integers(min_value=0, max_value=3),
    breakdown_is_disabled=st.booleans(),
    missing_value=st.booleans(),
)
def test_p23_factor_definitions_and_dependencies_are_all_or_nothing(
    field_count: int,
    transformation_count: int,
    breakdown_is_disabled: bool,
    missing_value: bool,
) -> None:
    definition_fields = tuple(f"input-field-{field_index}" for field_index in range(field_count))
    transformations = tuple(
        FactorTransformation(
            name="rank",
            parameters=((f"parameter-{parameter_index}", Decimal(parameter_index)),),
        )
        for parameter_index in range(transformation_count)
    )
    definition = FactorDefinition(
        definition_id="factor-1",
        version_id="v1",
        snapshot_schema_version="schema-v1",
        input_fields=definition_fields,
        primary_input_field=definition_fields[0],
        observation_window=1,
        transformations=transformations,
        missing_value_rule="EXCLUDE",
        extreme_value_rule="WINSORIZE",
        standardization_rule="ZSCORE",
        neutralization_rule="NONE",
        transformation_specification_version="spec-v1",
    )
    validate_factor_definition(definition)

    with TemporaryDirectory() as folder:
        persistence = ParquetFactorResearchRepository(Path(folder))
        factors = FactorService(persistence)
        stored = factors.create(definition)
        persisted_definition_count = len(persistence.list())
        assert persisted_definition_count == 1
        assert persistence.list()[0].definition_id == stored.definition_id

        evaluation = FactorEvaluationRequest(
            definition=stored,
            snapshot_id="snapshot-1",
            snapshot_schema_version="schema-v1",
            universe_version="universe-v1",
            factor_date=date(2025, 1, 2),
            decision_at=datetime(2025, 1, 2, 12, tzinfo=UTC),
            inputs=(
                FactorInput(
                    input_version_id="input-1",
                    field_name=definition_fields[0],
                    canonical_asset_id="ASSET-A",
                    observation_date=date(2025, 1, 1),
                    value=None if missing_value else Decimal("105.25"),
                    available_at=datetime(2025, 1, 1, 12, tzinfo=UTC),
                ),
            ),
        )
        if breakdown_is_disabled:
            evaluation = FactorEvaluationRequest(
                definition=stored,
                snapshot_id="snapshot-1",
                snapshot_schema_version="schema-v1",
                universe_version="universe-v1",
                factor_date=date(2025, 1, 2),
                decision_at=datetime(2025, 1, 2, 12, tzinfo=UTC),
                inputs=(),
            )
        result = factors.evaluate(evaluation)
        if breakdown_is_disabled:
            assert result.values == ()
            assert persistence.list_results(stored.definition_id) == []
        else:
            assert len(result.values) == 1
            if missing_value:
                assert result.values[0].status == "MISSING"
                assert result.values[0].value is None
                persisted_results = persistence.list_results(stored.definition_id)
                assert len(persisted_results) == 1
                assert persisted_results[0].status == "MISSING"
            else:
                assert result.values[0].status == "OK"
                assert result.values[0].value == Decimal("105.25")
                assert len(persistence.list_results(stored.definition_id)) == 1
