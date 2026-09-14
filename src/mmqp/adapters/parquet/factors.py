from __future__ import annotations

from builtins import list as list_type
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast

import pyarrow as pa
import pyarrow.parquet as pq

from mmqp.domain.errors import DomainError, ProblemV1
from mmqp.domain.factors import (
    FactorDefinition,
    FactorEvaluationRequest,
    FactorEvaluationResult,
    FactorValue,
)


class ParquetFactorResearchRepository:
    """Content-addressed Parquet artifacts for factor definitions and values."""

    def __init__(self, root_path: str | Path):
        self._root_path = Path(root_path)

    def create(self, definition: FactorDefinition) -> FactorDefinition:
        object_root = self._root_path / "factor_definitions"
        object_root.mkdir(parents=True, exist_ok=True)
        object_path = object_root / f"{definition.definition_id}.parquet"
        if object_path.exists():
            rows = _rows_from_table(pq.read_table(object_path))
            existing = rows[0]
            if existing["version_id"] == definition.version_id:
                return definition
            raise DomainError(
                ProblemV1(
                    kind="factor/definition-conflict",
                    title="Factor definition conflict",
                    status=409,
                    detail=f"factor definition {definition.definition_id} already exists",
                )
            )
        table = pa.Table.from_pylist([_row_from_definition(definition)], schema=_definition_schema())
        pq.write_table(table, object_path)
        return definition

    def list(self) -> list_type[FactorDefinition]:
        root = self._root_path / "factor_definitions"
        if not root.exists():
            return []
        definitions = [_definition_from_file(path) for path in root.glob("*.parquet")]
        definitions.sort(key=lambda definition: (definition.definition_id, definition.version_id))
        return definitions

    def find(self, definition_id: str) -> FactorDefinition | None:
        return next(
            (definition for definition in self.list() if definition.definition_id == definition_id), None
        )

    def create_result(
        self,
        request: FactorEvaluationRequest,
        result: FactorEvaluationResult,
    ) -> list_type[FactorValue]:
        values = [
            FactorValue(
                value_id=f"{request.definition.definition_id}:{request.factor_date}:{row.canonical_asset_id}",
                definition_id=request.definition.definition_id,
                definition_version=request.definition.version_id,
                snapshot_id=request.snapshot_id,
                universe_version=request.universe_version,
                factor_date=request.factor_date,
                decision_at=request.decision_at,
                canonical_asset_id=row.canonical_asset_id,
                data_quality_status=request.data_quality_status,
                status=row.status,
                value=row.value,
                observation_count=row.observation_count,
                required_count=row.required_count,
                details=row.details,
            )
            for row in result.values
        ]
        for value in values:
            object_root = self._root_path / "factor_values"
            object_root.mkdir(parents=True, exist_ok=True)
            object_path = object_root / f"{value.value_id}.parquet"
            table = pa.Table.from_pylist([_row_from_value(value)], schema=_value_schema())
            pq.write_table(table, object_path)
        return values

    def list_results(self, definition_id: str) -> list_type[FactorValue]:
        root = self._root_path / "factor_values"
        if not root.exists():
            return []
        values = [_value_from_file(path) for path in root.glob("*.parquet")]
        return [value for value in values if value.definition_id == definition_id]


def _definition_schema() -> pa.Schema:
    return pa.schema(
        [
            ("definition_id", pa.string()),
            ("version_id", pa.string()),
            ("snapshot_schema_version", pa.string()),
            ("input_fields_json", pa.string()),
            ("primary_input_field", pa.string()),
            ("observation_window", pa.int32()),
            ("transformations_json", pa.string()),
            ("missing_value_rule", pa.string()),
            ("extreme_value_rule", pa.string()),
            ("standardization_rule", pa.string()),
            ("neutralization_rule", pa.string()),
            ("transformation_specification_version", pa.string()),
        ]
    )


def _value_schema() -> pa.Schema:
    return pa.schema(
        [
            ("value_id", pa.string()),
            ("definition_id", pa.string()),
            ("definition_version", pa.string()),
            ("snapshot_id", pa.string()),
            ("universe_version", pa.string()),
            ("factor_date", pa.date32()),
            ("decision_at", pa.timestamp("us", tz="UTC")),
            ("canonical_asset_id", pa.string()),
            ("data_quality_status", pa.string()),
            ("status", pa.string()),
            ("value", pa.decimal128(38, 18)),
            ("observation_count", pa.int32()),
            ("required_count", pa.int32()),
        ]
    )


def _row_from_definition(definition: FactorDefinition) -> dict[str, str | int]:
    return {
        "definition_id": definition.definition_id,
        "version_id": definition.version_id,
        "snapshot_schema_version": definition.snapshot_schema_version,
        "input_fields_json": "\x1f".join(definition.input_fields),
        "primary_input_field": definition.primary_input_field,
        "observation_window": definition.observation_window,
        "transformations_json": "\x1f".join(
            f"{item.name}:{item.parameters}" for item in definition.transformations
        ),
        "missing_value_rule": definition.missing_value_rule,
        "extreme_value_rule": definition.extreme_value_rule,
        "standardization_rule": definition.standardization_rule,
        "neutralization_rule": definition.neutralization_rule,
        "transformation_specification_version": definition.transformation_specification_version,
    }


def _row_from_value(value: FactorValue) -> dict[str, str | int | date | datetime | Decimal | None]:
    return {
        "value_id": value.value_id,
        "definition_id": value.definition_id,
        "definition_version": value.definition_version,
        "snapshot_id": value.snapshot_id,
        "universe_version": value.universe_version,
        "factor_date": value.factor_date,
        "decision_at": value.decision_at,
        "canonical_asset_id": value.canonical_asset_id,
        "data_quality_status": value.data_quality_status,
        "status": value.status,
        "value": value.value,
        "observation_count": value.observation_count,
        "required_count": value.required_count,
    }


def _definition_from_file(path: Path) -> FactorDefinition:
    row = _rows_from_table(pq.read_table(path))[0]
    return FactorDefinition(
        definition_id=cast(str, row["definition_id"]),
        version_id=cast(str, row["version_id"]),
        snapshot_schema_version=cast(str, row["snapshot_schema_version"]),
        input_fields=tuple(cast(str, row["input_fields_json"]).split("\x1f")),
        primary_input_field=cast(str, row["primary_input_field"]),
        observation_window=cast(int, row["observation_window"]),
        transformations=(),
        missing_value_rule=cast("Literal['EXCLUDE', 'FAIL']", row["missing_value_rule"]),
        extreme_value_rule=cast("Literal['NONE', 'WINSORIZE']", row["extreme_value_rule"]),
        standardization_rule=cast("Literal['NONE', 'ZSCORE']", row["standardization_rule"]),
        neutralization_rule=cast("Literal['NONE', 'OLS']", row["neutralization_rule"]),
        transformation_specification_version=cast(str, row["transformation_specification_version"]),
    )


def _rows_from_table(table: pa.Table) -> list[dict[str, str | int | None]]:
    rows = table.to_pylist()
    return [{key: value for key, value in row.items()} for row in rows]


def _value_from_file(path: Path) -> FactorValue:
    row = _rows_from_table(pq.read_table(path))[0]
    return FactorValue(
        value_id=cast(str, row["value_id"]),
        definition_id=cast(str, row["definition_id"]),
        definition_version=cast(str, row["definition_version"]),
        snapshot_id=cast(str, row["snapshot_id"]),
        universe_version=cast(str, row["universe_version"]),
        factor_date=cast(date, row["factor_date"]),
        decision_at=cast(datetime, row["decision_at"]),
        canonical_asset_id=cast(str, row["canonical_asset_id"]),
        data_quality_status=cast(str, row["data_quality_status"]),
        status=cast("Literal['OK', 'MISSING', 'UNDEFINED']", row["status"]),
        value=cast(Decimal | None, row["value"]),
        observation_count=cast(int, row["observation_count"]),
        required_count=cast(int, row["required_count"]),
    )
