from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256

from mmqp.domain.factors import (
    MAX_INPUT_FIELDS,
    MAX_OBSERVATION_WINDOW,
    MAX_TRANSFORMATIONS,
    SUPPORTED_TRANSFORMATIONS,
    FactorDefinition,
    FactorDefinitionValidationError,
    FactorEvaluationRequest,
    FactorEvaluationResult,
    FactorInput,
    FactorResult,
    FactorTransformation,
)
from mmqp.domain.universes import aware_decision_at
from mmqp.ports.factors import FactorResearchRepository


class FactorService:
    def __init__(self, repository: FactorResearchRepository | None = None):
        self._repository = repository

    def create(self, definition: FactorDefinition) -> FactorDefinition:
        validate_factor_definition(definition)
        if definition.content_id is None:
            definition = _with_content_id(definition)
        if self._repository is None:
            return definition
        return self._repository.create(definition)

    def list(self) -> list[FactorDefinition]:
        if self._repository is None:
            return []
        return self._repository.list()

    def find(self, definition_id: str) -> FactorDefinition | None:
        if self._repository is None:
            return None
        return self._repository.find(definition_id)

    def evaluate(self, request: FactorEvaluationRequest) -> FactorEvaluationResult:
        decision_at = aware_decision_at(request.decision_at)
        if decision_at is None:
            raise ValueError("decision timestamp is required")
        request = replace(request, decision_at=decision_at)
        if self._repository is None:
            return evaluate_factor(request)
        result = evaluate_factor(request)
        self._repository.create_result(request, result)
        return result


def validate_factor_definition(definition: FactorDefinition) -> None:
    fields: list[str] = []
    if not definition.definition_id.strip() or not definition.version_id.strip():
        fields.append("definition_id")
    if not definition.snapshot_schema_version.strip():
        fields.append("snapshot_schema_version")
    if not definition.transformation_specification_version.strip():
        fields.append("transformation_specification_version")
    if not 1 <= len(definition.input_fields) <= MAX_INPUT_FIELDS:
        fields.append("input_fields")
    if definition.primary_input_field not in definition.input_fields:
        fields.append("primary_input_field")
    if not 1 <= definition.observation_window <= MAX_OBSERVATION_WINDOW:
        fields.append("observation_window")
    if not 0 <= len(definition.transformations) <= MAX_TRANSFORMATIONS:
        fields.append("transformations")
    for index, transformation in enumerate(definition.transformations):
        if transformation.name not in SUPPORTED_TRANSFORMATIONS:
            fields.append(f"transformations.{index}.name")
        if transformation.name == "winsorize":
            lower = _parameter(transformation, "q_lower")
            upper = _parameter(transformation, "q_upper")
            if lower is None or upper is None:
                fields.append(f"transformations.{index}.parameters")
            elif lower < 0 or upper > 1 or lower >= upper:
                fields.append(f"transformations.{index}.parameters")
    if fields:
        raise FactorDefinitionValidationError(fields)


def factor_definition_content_id(definition: FactorDefinition) -> str:
    definition = _with_content_id(definition)
    assert definition.content_id is not None
    return f"sha256:{sha256(definition.content_id.encode('utf-8')).hexdigest()}"


def _with_content_id(
    definition: FactorDefinition, value_id: str = "factor-definition-content"
) -> FactorDefinition:
    if definition.content_id:
        return definition
    material = "\x1f".join(
        (
            definition.definition_id,
            definition.version_id,
            definition.snapshot_schema_version,
            "\x1f".join(definition.input_fields),
            definition.primary_input_field,
            str(definition.observation_window),
            "\x1f".join(f"{item.name}:{item.parameters}" for item in definition.transformations),
            definition.missing_value_rule,
            definition.extreme_value_rule,
            definition.standardization_rule,
            definition.neutralization_rule,
            definition.transformation_specification_version,
        )
    )
    content_id = f"sha256:{sha256(f'{value_id}\x1f{material}'.encode()).hexdigest()[:20].upper()}"
    return replace(
        definition,
        content_id=content_id,
    )


def evaluate_factor(request: FactorEvaluationRequest) -> FactorEvaluationResult:
    grouped: dict[str, dict[str, list[FactorInput]]] = {}
    available = [value for value in request.inputs if value.available_at <= request.decision_at]
    for value in available:
        grouped.setdefault(value.canonical_asset_id, {}).setdefault(value.field_name, []).append(value)
    for rows_by_field in grouped.values():
        for rows in rows_by_field.values():
            rows.sort(
                key=lambda value: (
                    -0 if value.observation_date <= request.factor_date else 1,
                    value.observation_date,
                    value.available_at,
                    value.input_version_id,
                )
            )
    values: list[FactorResult] = []
    for canonical_asset_id in sorted(grouped):
        rows_by_field = grouped[canonical_asset_id]
        field_rows = rows_by_field.get(request.definition.primary_input_field, [])
        eligible = [row for row in field_rows if row.observation_date <= request.factor_date]
        current = eligible[-1] if eligible else None
        if current is None or current.value is None:
            values.append(
                FactorResult(
                    status="MISSING",
                    canonical_asset_id=canonical_asset_id,
                    value=None,
                    observation_count=0,
                    required_count=1,
                    details=("primary input unavailable",),
                )
            )
            continue
        values.append(
            FactorResult(
                status="OK",
                canonical_asset_id=canonical_asset_id,
                value=current.value,
                observation_count=1,
                required_count=1,
                details=(),
            )
        )
    return FactorEvaluationResult(
        factor_date=request.factor_date,
        decision_at=request.decision_at,
        universe_version=request.universe_version,
        values=tuple(values),
    )


def _parameter(transformation: FactorTransformation, name: str) -> Decimal | None:
    for key, value in transformation.parameters:
        if key == name:
            return value
    return None


def _winsorize_value(
    value: Decimal,
    values: Sequence[Decimal],
    q_lower: Decimal,
    q_upper: Decimal,
    observation_length: int,
) -> Decimal | None:
    if not value.is_finite():
        return None
    valid_values = sorted(
        comparison_value
        for comparison_value in values
        if comparison_value is not None and comparison_value.is_finite()
    )
    if not valid_values:
        return None
    upper_position = (
        int((Decimal(max(len(valid_values) - 1, 0)) * q_upper).to_integral_value(rounding="ROUND_FLOOR")) + 1
    )
    lower_position = (
        int((Decimal(max(len(valid_values) - 1, 0)) * q_lower).to_integral_value(rounding="ROUND_FLOOR")) + 1
    )
    lower_bound = valid_values[lower_position - 1]
    upper_bound = valid_values[upper_position - 1]
    return min(max(value, lower_bound), upper_bound)


def _winsorize_values(
    values: Sequence[Decimal | None],
    q_lower: Decimal,
    q_upper: Decimal,
    observation_length: int,
) -> Sequence[Decimal | None] | None:
    if any(comparison_value is None for comparison_value in values):
        return tuple(None for _ in values)
    if not q_lower.is_finite() or not q_upper.is_finite():
        return tuple(None for _ in values)
    if q_lower < 0 or q_upper > 1 or q_lower > q_upper:
        return None
    valid_values = [position_value for position_value in values if position_value is not None]
    results: list[Decimal | None] = []
    for value in values:
        if value is None:
            results.append(None)
        else:
            assert value.is_finite()
            results.append(
                _winsorize_value(
                    value,
                    valid_values,
                    q_lower,
                    q_upper,
                    observation_length,
                )
            )
    return tuple(results)


def _zscore_values(values: Sequence[Decimal]) -> Sequence[Decimal] | None:
    if len(values) < 2:
        return None
    mean = sum(values, Decimal(0)) / Decimal(len(values))
    variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values))
    if variance == 0:
        return None
    standardized_deviation = variance.sqrt()
    return [(value - mean) / standardized_deviation for value in values]
