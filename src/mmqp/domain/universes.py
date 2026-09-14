from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Literal

from mmqp.domain.errors import DomainError, ProblemV1


@dataclass(frozen=True, slots=True)
class UniverseMembership:
    membership_id: str
    universe_version: str
    canonical_asset_id: str
    effective_from: date
    effective_to: date | None
    membership_source: str
    source_version: str


@dataclass(frozen=True, slots=True)
class LifecycleVersion:
    version_id: str
    canonical_asset_id: str
    effective_from: date
    effective_to: date | None
    lifecycle_status: str


@dataclass(frozen=True, slots=True)
class LiquidityInput:
    input_version_id: str
    canonical_asset_id: str
    available_at: datetime
    value: Decimal | None


@dataclass(frozen=True, slots=True)
class UniverseExclusion:
    canonical_asset_id: str
    reason: Literal["MISSING", "AMBIGUOUS", "LIFECYCLE", "LIQUIDITY", "MAPPING"]
    details: str
    factor_date: date | None = None
    decision_at: datetime | None = None
    evaluated_membership_version: str | None = None


@dataclass(frozen=True, slots=True)
class SurvivorshipWarning:
    universe_version: str
    incomplete_from: date
    incomplete_to: date
    missing_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LookaheadBiasPrevention:
    canonical_asset_id: str
    input_version_id: str
    provider_available_at: datetime
    decision_at: datetime
    exclusion_reason: str


@dataclass(frozen=True, slots=True)
class UniverseSelection:
    included: tuple[str, ...]
    excluded: tuple[UniverseExclusion, ...]
    factor_date: date | None = None
    decision_at: datetime | None = None
    universe_version: str | None = None
    member_count: int = 0
    exclusion_counts: dict[str, int] = field(default_factory=dict)
    survivorship_warnings: tuple[SurvivorshipWarning, ...] = ()
    lookahead_preventions: tuple[LookaheadBiasPrevention, ...] = ()


class UniverseMembershipValidationError(DomainError):
    def __init__(self, fields: list[str]):
        super().__init__(
            ProblemV1(
                kind="universe/membership-invalid",
                title="Universe membership invalid",
                status=400,
                detail=f"universe membership invalid: {', '.join(fields)}",
            )
        )
        self.fields = fields


def membership_content_id(membership: UniverseMembership) -> str:
    canonical = "\x1f".join(
        (
            membership.membership_id,
            membership.universe_version,
            membership.canonical_asset_id,
            membership.effective_from.isoformat(),
            "" if membership.effective_to is None else membership.effective_to.isoformat(),
            membership.membership_source,
            membership.source_version,
        )
    )
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


def validate_membership(membership: UniverseMembership) -> None:
    fields: list[str] = []
    if not membership.membership_id.strip():
        fields.append("membership_id")
    if not membership.universe_version.strip():
        fields.append("universe_version")
    if not membership.canonical_asset_id.strip():
        fields.append("canonical_asset_id")
    if not membership.membership_source.strip():
        fields.append("membership_source")
    if not membership.source_version.strip():
        fields.append("source_version")
    if membership.effective_to is not None and membership.effective_to < membership.effective_from:
        fields.append("effective_to")
    if fields:
        raise UniverseMembershipValidationError(fields)


def parse_liquidity_value(raw: object) -> Decimal | None:
    if raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    return value if value.is_finite() else None


def aware_decision_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class UnavailableMembershipSourceError(DomainError):
    def __init__(self, fields: list[str]):
        super().__init__(
            ProblemV1(
                kind="universe/membership-source-unavailable",
                title="Universe membership source unavailable",
                status=400,
                detail=f"universe membership source unavailable: {', '.join(fields)}",
            )
        )
        self.fields = fields
