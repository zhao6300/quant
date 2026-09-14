from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from mmqp.adapters.parquet.factors import ParquetFactorResearchRepository
from mmqp.application.factors import FactorService, _with_content_id, validate_factor_definition
from mmqp.domain.factors import (
    FactorDefinition,
    FactorDefinitionValidationError,
    FactorEvaluationRequest,
    FactorInput,
    FactorTransformation,
)


def _definition() -> FactorDefinition:
    return FactorDefinition(
        definition_id="price-reversal",
        version_id="v1",
        snapshot_schema_version="schema-v1",
        input_fields=("daily_bar_close",),
        primary_input_field="daily_bar_close",
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


def test_definition_accepts_valid_aliases_and_values() -> None:
    definition = _definition()
    validate_factor_definition(definition)
    assert _with_content_id(definition).content_id is not None


def test_evaluation_treats_missing_value_as_missing() -> None:
    definition = _definition()
    result = FactorService().evaluate(
        FactorEvaluationRequest(
            definition=definition,
            snapshot_id="snapshot-1",
            snapshot_schema_version="schema-v1",
            universe_version="universe-v1",
            factor_date=date(2025, 1, 2),
            decision_at=datetime(2025, 1, 2, 12, tzinfo=UTC),
            inputs=(),
        )
    )
    assert result.values == ()


def test_definition_rejects_invalid_primary_field() -> None:
    with pytest.raises(FactorDefinitionValidationError):
        FactorService().create(replace(_definition(), primary_input_field="other-field"))


def test_factor_values_persist_with_snapshot_and_universe() -> None:
    definition = _definition()
    with TemporaryDirectory() as folder:
        repository = ParquetFactorResearchRepository(Path(folder))
        service = FactorService(repository)
        stored_definition = service.create(definition)
        stored_result = FactorService(repository).evaluate(
            FactorEvaluationRequest(
                definition=stored_definition,
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
                        value=Decimal("105.25"),
                        available_at=datetime(2025, 1, 1, 20, tzinfo=UTC),
                    ),
                ),
            ),
        )
        values = repository.list_results(stored_definition.definition_id)
        assert stored_result.decision_at == datetime(2025, 1, 2, 12, tzinfo=UTC)
        assert len(values) == 1
        assert values[0].value == Decimal("105.25")


@dataclass(frozen=True, slots=True)
class FactorEvaluationRequest2:
    id: str
    name: str
    factor_date: date
    data: tuple[object, ...]
    status: str = "OK"
    decision_at: str = ""
    ic: Decimal | None = None
    spearman_ic: Decimal | None = None
    quantile_returns: tuple[tuple[str, Decimal], ...] = ()
    quantiles: tuple[int, ...] = ()
