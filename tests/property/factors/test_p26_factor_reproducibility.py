from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mmqp.adapters.parquet.factors import ParquetFactorResearchRepository
from mmqp.application.factors import FactorService
from mmqp.domain.factors import FactorDefinition, FactorEvaluationRequest, FactorInput, FactorTransformation


def _definition(value_count: int) -> FactorDefinition:
    return FactorDefinition(
        definition_id="factor-reprod",
        version_id="v1",
        snapshot_schema_version="schema-v1",
        input_fields=("close",),
        primary_input_field="close",
        observation_window=1,
        transformations=(
            FactorTransformation(
                name="winsorize",
                parameters=(("q_lower", Decimal("0.05")), ("q_upper", Decimal("0.95"))),
            ),
        ),
        missing_value_rule="EXCLUDE",
        extreme_value_rule="WINSORIZE",
        standardization_rule="ZSCORE",
        neutralization_rule="NONE",
        transformation_specification_version="spec-v1",
    )


@settings(
    max_examples=5,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    value_count=st.integers(min_value=1, max_value=3),
    edge_case=st.booleans(),
)
def test_factor_evaluation_is_reproducible(value_count: int, edge_case: bool) -> None:
    factor_date = date(2025, 1, 2)
    decision_at = datetime(2025, 1, 2, 12, tzinfo=UTC)
    inputs = [
        FactorInput(
            "input-1", "close", "ASSET-A", date(2025, 1, 1), Decimal("1"), decision_at - timedelta(days=1)
        )
    ]
    if edge_case:
        inputs.append(FactorInput("input-2", "close", "ASSET-B", date(2025, 1, 2), Decimal("2"), decision_at))
        inputs.append(
            FactorInput(
                "input-3", "close", "ASSET-C", date(2025, 1, 3), Decimal("3"), decision_at + timedelta(days=1)
            )
        )
    request = FactorEvaluationRequest(
        definition=_definition(value_count),
        snapshot_id=f"snapshot-{value_count}",
        snapshot_schema_version="schema-v1",
        universe_version="universe-v1",
        factor_date=factor_date,
        decision_at=decision_at,
        inputs=tuple(inputs),
    )
    with TemporaryDirectory() as folder:
        persistence = ParquetFactorResearchRepository(Path(folder))
        service = FactorService(persistence)
        definition = service.create(request.definition)
        request = replace(request, definition=definition)
        first = service.evaluate(request)
        second = service.evaluate(request)
        assert first.factor_date == second.factor_date
        assert first.decision_at == second.decision_at
        assert first.values == second.values
        assert persistence.list_results(definition.definition_id) == persistence.list_results(
            definition.definition_id
        )
