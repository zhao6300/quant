from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from mmqp.domain.errors import DomainError, ProblemV1

FactorStatus = Literal["OK", "MISSING", "UNDEFINED"]
TransformationName = Literal[
    "identity",
    "lag",
    "simple_return",
    "log_return",
    "rolling_mean",
    "rolling_std",
    "ratio",
    "difference",
    "rank",
    "winsorize",
    "zscore",
    "neutralize_ols",
]
MissingValueRule = Literal["EXCLUDE", "FAIL"]
ExtremeValueRule = Literal["NONE", "WINSORIZE"]
StandardizationRule = Literal["NONE", "ZSCORE"]
NeutralizationRule = Literal["NONE", "OLS"]

SUPPORTED_TRANSFORMATIONS: tuple[TransformationName, ...] = (
    "identity",
    "lag",
    "simple_return",
    "log_return",
    "rolling_mean",
    "rolling_std",
    "ratio",
    "difference",
    "rank",
    "winsorize",
    "zscore",
    "neutralize_ols",
)
MAX_INPUT_FIELDS = 64
MAX_TRANSFORMATIONS = 32
MAX_OBSERVATION_WINDOW = 2520


@dataclass(frozen=True, slots=True)
class FactorTransformation:
    name: TransformationName
    parameters: tuple[tuple[str, Decimal], ...] = ()


@dataclass(frozen=True, slots=True)
class TransformationSpecification:
    version_id: str
    names: tuple[TransformationName, ...]


@dataclass(frozen=True, slots=True)
class FactorDefinition:
    definition_id: str
    version_id: str
    snapshot_schema_version: str
    input_fields: tuple[str, ...]
    primary_input_field: str
    observation_window: int
    transformations: tuple[FactorTransformation, ...]
    missing_value_rule: MissingValueRule
    extreme_value_rule: ExtremeValueRule
    standardization_rule: StandardizationRule
    neutralization_rule: NeutralizationRule
    transformation_specification_version: str
    content_id: str | None = None


class FactorDefinitionValidationError(DomainError):
    def __init__(self, fields: list[str]):
        super().__init__(
            ProblemV1(
                kind="factor/definition-invalid",
                title="Factor definition invalid",
                status=422,
                detail=f"factor definition rule violations: {', '.join(fields)}",
            )
        )
        self.fields = fields


@dataclass(frozen=True, slots=True)
class FactorInput:
    input_version_id: str
    field_name: str
    canonical_asset_id: str
    observation_date: date
    value: Decimal | None
    available_at: datetime


@dataclass(frozen=True, slots=True)
class ExposureInput:
    input_version_id: str
    exposure_name: str
    canonical_asset_id: str
    value: Decimal | None
    available_at: datetime


@dataclass(frozen=True, slots=True)
class FactorEvaluationRequest:
    definition: FactorDefinition
    snapshot_id: str
    snapshot_schema_version: str
    universe_version: str
    factor_date: date
    decision_at: datetime
    inputs: tuple[FactorInput, ...]
    exposures: tuple[ExposureInput, ...] = ()
    data_quality_status: str = "VALID"


@dataclass(frozen=True, slots=True)
class FactorDependency:
    dependency_id: str
    field_name: str
    canonical_asset_id: str
    note: str


@dataclass(frozen=True, slots=True)
class FactorResult:
    status: FactorStatus
    canonical_asset_id: str
    value: Decimal | None
    observation_count: int
    required_count: int
    details: tuple[str, ...] = ()
    dependencies: tuple[FactorDependency, ...] = ()
    data_quality_status: str = "VALID"


@dataclass(frozen=True, slots=True)
class FactorEvaluationResult:
    factor_date: date
    decision_at: datetime
    universe_version: str
    values: tuple[FactorResult, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FactorValue:
    value_id: str
    definition_id: str
    definition_version: str
    snapshot_id: str
    universe_version: str
    factor_date: date
    decision_at: datetime
    canonical_asset_id: str
    data_quality_status: str
    status: FactorStatus
    value: Decimal | None
    observation_count: int
    required_count: int
    details: tuple[str, ...] = ()


class FactorEvaluationValidationError(DomainError):
    def __init__(self, fields: list[str]):
        super().__init__(
            ProblemV1(
                kind="factor/evaluation-invalid",
                title="Factor evaluation validation invalid",
                status=422,
                detail=f"factor evaluation invalid: {', '.join(fields)}",
            )
        )
        self.fields = fields


@dataclass(frozen=True, slots=True)
class Scale:
    values: tuple[Decimal, ...]


def evaluate_scale(scale: Scale) -> Decimal:
    return sum(scale.values, Decimal("0"))
