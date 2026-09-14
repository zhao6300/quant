from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from mmqp.domain.errors import DomainError, ProblemV1

QualityStatus = Literal["valid", "warning", "rejected"]
QualityIssueStatus = Literal["valid", "warning", "rejected"]
GapReason = Literal[
    "expected-calendar-gap",
    "suspended-trading-gap",
    "delayed-or-missing-valuation",
    "unresolved-market-data-gap",
]
QUALITY_STATUSES: tuple[QualityStatus, ...] = ("valid", "warning", "rejected")
GAP_PRECEDENCE: tuple[GapReason, ...] = (
    "suspended-trading-gap",
    "delayed-or-missing-valuation",
    "unresolved-market-data-gap",
    "expected-calendar-gap",
)


@dataclass(frozen=True, slots=True)
class QualityRule:
    rule_id: str
    rule_kind: Literal[
        "uniqueness",
        "required_fields",
        "numeric_ranges",
        "date_validity",
        "currency_consistency",
        "unit_consistency",
        "lifecycle_consistency",
        "mapping_resolution",
        "provider_timestamp_order",
    ]
    version: str
    severity: QualityIssueStatus
    applicable_to: frozenset[Literal["DAILY_BAR", "FUND_NAV", "FUNDAMENTAL_FACT"]]
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class QualityIssue:
    rule_id: str
    rule_version: str
    severity: QualityIssueStatus
    canonical_asset_id: str | None
    observation_date: date | None
    field: str | None
    observed_value: Decimal | str | None
    expected_condition: str
    unavailable_dependency: str | None
    evidence: str


@dataclass(frozen=True, slots=True)
class GapCondition:
    reason: GapReason


@dataclass(frozen=True, slots=True)
class ComplianceContext:
    source: str
    prices: Mapping[str, Decimal]
    approvals: frozenset[str]
    actions: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class RejectedConfirmation:
    snapshot_id: str
    rejected_version_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class QualityCounts:
    valid: int
    warning: int
    rejected: int


@dataclass(frozen=True, slots=True)
class QualityReport:
    report_id: str
    scope: str
    rule_set_version: str
    issues: frozenset[QualityIssue] | tuple[QualityIssue, ...]
    status: QualityStatus
    counts: QualityCounts
    generated_at: datetime


class QualityConfigurationError(DomainError):
    def __init__(self, fields: list[str]):
        super().__init__(
            ProblemV1(
                kind="quality/configuration-invalid",
                title="Quality policy invalid",
                status=400,
                detail=f"quality policy invalid: {', '.join(fields)}",
            )
        )
        self.fields = fields
