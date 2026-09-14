from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from mmqp.domain.universes import (
    LifecycleVersion,
    LiquidityInput,
    LookaheadBiasPrevention,
    SurvivorshipWarning,
    UniverseExclusion,
    UniverseMembership,
    UniverseSelection,
    aware_decision_at,
    parse_liquidity_value,
    validate_membership,
)
from mmqp.ports.universes import UniverseMembershipRepository

_RESERVED_SOURCES: frozenset[str] = frozenset({"UNKNOWN"})


class UniverseService:
    def __init__(self, repository: UniverseMembershipRepository | None = None):
        self._repository = repository

    def create(self, membership: UniverseMembership) -> UniverseMembership:
        validate_membership(membership)
        if self._repository is None:
            return membership
        return self._repository.create(membership)

    def list(self) -> list[UniverseMembership]:
        if self._repository is None:
            return []
        return self._repository.list()

    def find(self, membership_id: str) -> UniverseMembership | None:
        if self._repository is None:
            return None
        return self._repository.find(membership_id)

    @staticmethod
    def select(
        memberships: Sequence[UniverseMembership],
        universe_version: str,
        factor_date: date,
        decision_at: datetime | None = None,
        lifecycles: Sequence[LifecycleVersion] | None = None,
        liquidity: Sequence[LiquidityInput] | None = None,
    ) -> UniverseSelection:
        return select_universe(
            memberships=memberships,
            universe_version=universe_version,
            factor_date=factor_date,
            decision_at=decision_at,
            lifecycles=lifecycles,
            liquidity=liquidity,
        )

    @staticmethod
    def select_history(
        memberships: Sequence[UniverseMembership],
        universe_version: str,
        requested_dates: Sequence[date],
        decision_at: datetime | None = None,
        lifecycles: Sequence[LifecycleVersion] | None = None,
        liquidity: Sequence[LiquidityInput] | None = None,
    ) -> UniverseSelection:
        return select_universe_history(
            memberships=memberships,
            universe_version=universe_version,
            requested_dates=requested_dates,
            decision_at=decision_at,
            lifecycles=lifecycles,
            liquidity=liquidity,
        )


def select_universe(
    memberships: Sequence[UniverseMembership],
    universe_version: str,
    factor_date: date,
    *,
    decision_at: datetime | None = None,
    lifecycles: Sequence[LifecycleVersion] | None = None,
    liquidity: Sequence[LiquidityInput] | None = None,
) -> UniverseSelection:
    """Select canonical assets with exactly one PIT-valid, date-effective membership."""
    grouped = _group_memberships(memberships, universe_version)
    included: list[str] = []
    exclusions: list[UniverseExclusion] = []
    lookahead_preventions: list[LookaheadBiasPrevention] = []
    decision_at = aware_decision_at(decision_at)

    for canonical_asset_id in sorted(grouped):
        matching = _matching_memberships(grouped[canonical_asset_id], factor_date)
        if len(matching) != 1:
            exclusions.append(
                _membership_exclusion(
                    canonical_asset_id,
                    factor_date,
                    decision_at,
                    matching,
                )
            )
            continue
        membership_evidence = matching[0]
        unavailable: list[tuple[str, str]] = []
        if lifecycles is not None:
            lifecycle = _lifecycle_assessment(
                lifecycles,
                canonical_asset_id=canonical_asset_id,
                factor_date=factor_date,
            )
            if lifecycle.status != "ACTIVE":
                unavailable.append(("LIFECYCLE", lifecycle.details))
        if liquidity is not None and not unavailable:
            liquidity_assessment = _liquidity_assessment(
                liquidity,
                canonical_asset_id=canonical_asset_id,
                decision_at=decision_at,
            )
            lookahead_preventions.extend(liquidity_assessment.future_preventions)
            if liquidity_assessment.unavailable_categories:
                unavailable.append(("LIQUIDITY", "; ".join(liquidity_assessment.unavailable_categories)))
        if unavailable:
            exclusion_reason = _exclusion_reason(unavailable[0][0])
            exclusions.append(
                UniverseExclusion(
                    canonical_asset_id=canonical_asset_id,
                    reason=exclusion_reason,
                    details="; ".join(details for _reason, details in unavailable),
                    factor_date=factor_date,
                    decision_at=decision_at,
                    evaluated_membership_version=membership_evidence.membership_id,
                )
            )
            continue
        included.append(canonical_asset_id)

    return UniverseSelection(
        included=tuple(included),
        excluded=tuple(exclusions),
        factor_date=factor_date,
        decision_at=decision_at,
        universe_version=universe_version,
        member_count=len(included),
        exclusion_counts=dict(Counter(exclusion.reason for exclusion in exclusions)),
        survivorship_warnings=_incompleteness_warnings(
            memberships,
            universe_version,
            (factor_date,),
        ),
        lookahead_preventions=tuple(lookahead_preventions),
    )


def select_universe_history(
    memberships: Sequence[UniverseMembership],
    universe_version: str,
    requested_dates: Sequence[date],
    *,
    decision_at: datetime | None = None,
    lifecycles: Sequence[LifecycleVersion] | None = None,
    liquidity: Sequence[LiquidityInput] | None = None,
) -> UniverseSelection:
    """Select PIT universes across ordered research dates with reconciled warnings."""
    requested_dates = sorted(set(requested_dates))
    if not requested_dates:
        return UniverseSelection(
            included=(),
            excluded=(),
            factor_date=None,
            decision_at=aware_decision_at(decision_at),
            universe_version=universe_version,
            member_count=0,
            exclusion_counts={},
        )
    date_selections = [
        select_universe(
            memberships=memberships,
            universe_version=universe_version,
            factor_date=factor_date,
            decision_at=decision_at,
            lifecycles=lifecycles,
            liquidity=liquidity,
        )
        for factor_date in requested_dates
    ]
    included = sorted({member for selection in date_selections for member in selection.included})
    lookahead_preventions = tuple(
        prevention for selection in date_selections for prevention in selection.lookahead_preventions
    )
    return UniverseSelection(
        included=tuple(included),
        excluded=date_selections[-1].excluded,
        factor_date=requested_dates[-1],
        decision_at=aware_decision_at(decision_at),
        universe_version=universe_version,
        member_count=len(included),
        exclusion_counts=_aggregate_exclusion_counts(date_selections),
        survivorship_warnings=_incompleteness_warnings(
            memberships,
            universe_version,
            requested_dates,
        ),
        lookahead_preventions=lookahead_preventions,
    )


@dataclass(frozen=True, slots=True)
class LifecycleAssessment:
    status: Literal["ACTIVE", "UNAVAILABLE"]
    details: str


@dataclass(frozen=True, slots=True)
class LiquidityAssessment:
    future_preventions: tuple[LookaheadBiasPrevention, ...]
    unavailable_categories: tuple[str, ...]


def _group_memberships(
    memberships: Sequence[UniverseMembership],
    universe_version: str,
) -> dict[str, list[UniverseMembership]]:
    grouped: dict[str, list[UniverseMembership]] = defaultdict(list)
    for membership in memberships:
        if membership.universe_version == universe_version:
            grouped[membership.canonical_asset_id].append(membership)
    for member_rows in grouped.values():
        member_rows.sort(
            key=lambda item: (
                item.effective_from,
                item.effective_to or item.effective_from,
                item.membership_id,
            ),
        )
    return grouped


def _matching_memberships(
    memberships: list[UniverseMembership],
    requested_date: date,
) -> list[UniverseMembership]:
    return [
        membership
        for membership in memberships
        if membership.effective_from <= requested_date
        and (membership.effective_to is None or membership.effective_to >= requested_date)
    ]


def _membership_exclusion(
    canonical_asset_id: str,
    factor_date: date,
    decision_at: datetime | None,
    matches: Sequence[UniverseMembership],
) -> UniverseExclusion:
    return UniverseExclusion(
        canonical_asset_id=canonical_asset_id,
        reason="AMBIGUOUS" if matches else "MISSING",
        details="overlapping membership intervals" if matches else "absent membership interval",
        factor_date=factor_date,
        decision_at=decision_at,
        evaluated_membership_version=matches[0].membership_id if matches else None,
    )


def _lifecycle_assessment(
    lifecycle_versions: Sequence[LifecycleVersion],
    canonical_asset_id: str,
    factor_date: date,
) -> LifecycleAssessment:
    effective = [
        lifecycle
        for lifecycle in lifecycle_versions
        if lifecycle.canonical_asset_id == canonical_asset_id
        and lifecycle.effective_from <= factor_date
        and (lifecycle.effective_to is None or lifecycle.effective_to >= factor_date)
    ]
    if len(effective) == 1:
        lifecycle = effective[0]
        if lifecycle.lifecycle_status == "ACTIVE":
            return LifecycleAssessment("ACTIVE", f"evaluated lifecycle version {lifecycle.version_id}")
        return LifecycleAssessment(
            "UNAVAILABLE",
            f"evaluated lifecycle version {lifecycle.version_id} status {lifecycle.lifecycle_status}",
        )
    return LifecycleAssessment(
        "UNAVAILABLE",
        "ambiguous lifecycle versions" if effective else "lifecycle version unavailable",
    )


def _liquidity_assessment(
    observations: Sequence[LiquidityInput],
    canonical_asset_id: str,
    decision_at: datetime | None,
) -> LiquidityAssessment:
    asset_observations = sorted(
        (observation for observation in observations if observation.canonical_asset_id == canonical_asset_id),
        key=lambda observation: (observation.available_at, observation.input_version_id),
    )
    unavailable_categories: list[str] = []
    if decision_at is None:
        unavailable_categories.append("decision timestamp unavailable")
        return LiquidityAssessment(
            future_preventions=(),
            unavailable_categories=tuple(unavailable_categories),
        )
    visible = [observation for observation in asset_observations if observation.available_at <= decision_at]
    future = [observation for observation in asset_observations if observation.available_at > decision_at]
    future_preventions = tuple(
        LookaheadBiasPrevention(
            canonical_asset_id=canonical_asset_id,
            input_version_id=observation.input_version_id,
            provider_available_at=observation.available_at,
            decision_at=decision_at,
            exclusion_reason="future liquidity observation excluded",
        )
        for observation in future
    )
    if not any(_liquidity_value(observation) is not None for observation in visible):
        unavailable_categories.append("visible liquidity value unavailable")
    return LiquidityAssessment(
        future_preventions=future_preventions,
        unavailable_categories=tuple(unavailable_categories),
    )


def _aggregate_exclusion_counts(selections: Sequence[UniverseSelection]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for selection in selections:
        counts.update(selection.exclusion_counts)
    return dict(counts)


def _liquidity_value(observation: LiquidityInput) -> Decimal | None:
    return parse_liquidity_value(observation.value)


def _exclusion_reason(category: str) -> Literal["LIFECYCLE", "LIQUIDITY"]:
    if category == "LIFECYCLE":
        return "LIFECYCLE"
    return "LIQUIDITY"


def _incompleteness_warnings(
    memberships: Sequence[UniverseMembership],
    universe_version: str,
    requested_dates: Sequence[date],
) -> tuple[SurvivorshipWarning, ...]:
    warnings: list[SurvivorshipWarning] = []
    grouped_by_asset: dict[str, list[UniverseMembership]] = defaultdict(list)
    for membership in memberships:
        if membership.universe_version == universe_version:
            grouped_by_asset[membership.canonical_asset_id].append(membership)
    for canonical_asset_id in sorted(grouped_by_asset):
        for membership_source in sorted(
            {item.membership_source for item in grouped_by_asset[canonical_asset_id]}
        ):
            if membership_source in _RESERVED_SOURCES:
                continue
            source_rows = sorted(
                (
                    row
                    for row in grouped_by_asset[canonical_asset_id]
                    if row.membership_source == membership_source
                ),
                key=lambda item: (item.effective_from, item.effective_to or item.effective_from),
            )
            incomplete_dates = [
                requested_date
                for requested_date in sorted(set(requested_dates))
                if _source_gap(source_rows, requested_date)
            ]
            warnings.extend(
                SurvivorshipWarning(
                    universe_version=universe_version,
                    incomplete_from=start,
                    incomplete_to=end,
                    missing_sources=(membership_source,),
                )
                for start, end in _contiguous_date_ranges(incomplete_dates)
            )
    return tuple(warnings)


def _source_gap(memberships: Sequence[UniverseMembership], requested_date: date) -> bool:
    earlier = [membership for membership in memberships if membership.effective_from <= requested_date]
    later = [
        membership
        for membership in memberships
        if membership.effective_to is None or membership.effective_to >= requested_date
    ]
    return bool(earlier and later and not _matching_memberships(list(memberships), requested_date))


def _contiguous_date_ranges(dates: Sequence[date]) -> tuple[tuple[date, date], ...]:
    if not dates:
        return ()
    ranges: list[tuple[date, date]] = []
    start = previous = dates[0]
    for current_date in dates[1:]:
        if (current_date - previous).days != 1:
            ranges.append((start, previous))
            start = current_date
        previous = current_date
    ranges.append((start, previous))
    return tuple(ranges)
