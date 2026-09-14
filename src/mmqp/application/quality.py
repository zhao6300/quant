from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timezone
from decimal import Decimal
from typing import cast

from mmqp.domain.ingestion import DailyBar, DatasetType, FundamentalFact, FundNav
from mmqp.domain.quality import (
    ComplianceContext,
    GapCondition,
    QualityConfigurationError,
    QualityCounts,
    QualityIssue,
    QualityReport,
    QualityRule,
    QualityStatus,
)
from mmqp.ports.calendars import TradingCalendarRepository, ValuationCalendarRepository


@dataclass(frozen=True, slots=True)
class QualityEvaluationResult:
    quality_status: QualityStatus
    quality_issues: tuple[QualityIssue, ...]
    identifier: str | None


@dataclass(frozen=True, slots=True)
class Gap:
    condition: GapCondition


class QualityService:
    def __init__(
        self,
        trading: TradingCalendarRepository | None = None,
        valuation: ValuationCalendarRepository | None = None,
        quality_policy: Mapping[str, str] | None = None,
    ) -> None:
        self._trading = trading
        self._valuation = valuation
        self._quality_policy = quality_policy or {}

    def evaluate(
        self,
        context: ComplianceContext,
        rules: tuple[QualityRule, ...],
    ) -> tuple[QualityIssue, ...]:
        return _evaluate_context(context, rules)

    def evaluate_daily_bar(
        self,
        observation: DailyBar,
        market: str,
        exchange: str,
        rules: frozenset[QualityRule],
        identity_mapping: bool = False,
    ) -> QualityEvaluationResult:
        validated_rules = self._validate_rules(rules)
        result = self._evaluate(observation, "DAILY_BAR", validated_rules, market, exchange)
        if identity_mapping:
            result = _evaluate_identity_mapping(result, observation.canonical_asset_id)
        return result

    def evaluate_fund_nav(
        self,
        observation: FundNav,
        market: str,
        rules: frozenset[QualityRule],
    ) -> QualityEvaluationResult:
        validated_rules = self._validate_rules(rules)
        return self._evaluate(observation, "FUND_NAV", validated_rules, market, None)

    def evaluate_fundamental_fact(
        self,
        observation: FundamentalFact,
        rules: frozenset[QualityRule],
    ) -> QualityEvaluationResult:
        validated_rules = self._validate_rules(rules)
        return self._evaluate(observation, "FUNDAMENTAL_FACT", validated_rules, None, None)

    def report(
        self,
        issues: tuple[QualityIssue, ...],
        rule_set_version: str,
        scope: str = "application/quality",
    ) -> QualityReport:
        if not rule_set_version.strip():
            raise QualityConfigurationError(["rule_set_version"])
        counts = _counts(issues)
        maximum = cast(
            QualityStatus,
            max(
                (issue.severity for issue in issues),
                key=lambda value: "valid warning rejected".split().index(value),
                default="valid",
            ),
        )
        return QualityReport(
            report_id=uuid.uuid4().hex,
            scope=scope,
            rule_set_version=rule_set_version,
            issues=tuple(issues),
            status=maximum,
            counts=counts,
            generated_at=_now(UTC),
        )

    def _validate_rules(
        self,
        rules: frozenset[QualityRule],
    ) -> tuple[QualityRule, ...]:
        if not rules:
            raise QualityConfigurationError(["rules"])
        return tuple(rules)

    def _evaluate(
        self,
        observation: DailyBar | FundNav | FundamentalFact,
        dataset_type: DatasetType,
        rules: tuple[QualityRule, ...],
        market: str | None,
        exchange: str | None,
    ) -> QualityEvaluationResult:
        issues = self._issues(observation, dataset_type, rules, market, exchange)
        return _aggregate(issues)

    def _issues(
        self,
        observation: DailyBar | FundNav | FundamentalFact,
        dataset_type: DatasetType,
        rules: tuple[QualityRule, ...],
        market: str | None,
        exchange: str | None,
    ) -> tuple[QualityIssue, ...]:
        del market, exchange
        return tuple(
            issue for rule in rules for issue in _observation_issues(observation, dataset_type, rule)
        )


def _aggregate(issues: tuple[QualityIssue, ...]) -> QualityEvaluationResult:
    if not issues:
        return QualityEvaluationResult(quality_status="valid", quality_issues=(), identifier=None)
    maximum = max(
        issues,
        key=lambda issue: "valid warning rejected".split().index(issue.severity),
    )
    return QualityEvaluationResult(
        quality_status=maximum.severity,
        quality_issues=issues,
        identifier=None,
    )


def _evaluate_context(
    context: ComplianceContext,
    rules: tuple[QualityRule, ...],
) -> tuple[QualityIssue, ...]:
    issues: list[QualityIssue] = []
    for index, rule in enumerate(rules, start=1):
        issue = _context_issue(context, index, rule)
        if issue is not None:
            issues.append(issue)
    return tuple(issues)


def _context_issue(
    context: ComplianceContext,
    index: int,
    rule: QualityRule,
) -> QualityIssue | None:
    del context, index, rule
    return None


def _observation_issues(
    observation: DailyBar | FundNav | FundamentalFact,
    dataset_type: DatasetType,
    rule: QualityRule,
) -> tuple[QualityIssue, ...]:
    issues: list[QualityIssue] = []
    if rule.rule_kind == "required_fields" and not _required_fields_present(observation):
        issues.append(_issue(rule, observation, None, None, "present", None, "missing field"))
    if rule.rule_kind == "numeric_ranges" and not _numeric_range_valid(observation):
        issues.append(_issue(rule, observation, None, None, "within bounds", None, "outside numeric bounds"))
    if rule.rule_kind == "date_validity" and not _date_valid(observation):
        issues.append(_issue(rule, observation, None, None, "supported date range", None, "unsupported date"))
    if rule.rule_kind == "currency_consistency" and not _currency_valid(observation):
        issues.append(_issue(rule, observation, None, None, "consistent currency", None, "currency mismatch"))
    if rule.rule_kind == "unit_consistency" and not _unit_valid(observation):
        issues.append(_issue(rule, observation, None, None, "consistent unit", None, "unit mismatch"))
    if rule.rule_kind == "lifecycle_consistency" and not _lifecycle_valid(observation):
        issues.append(
            _issue(rule, observation, None, None, "consistent lifecycle", None, "lifecycle mismatch")
        )
    if rule.rule_kind == "mapping_resolution" and not _mapping_valid(observation):
        issues.append(_issue(rule, observation, None, None, "resolved mapping", None, "mapping unresolved"))
    if rule.rule_kind == "provider_timestamp_order" and not _timestamp_order_valid(observation):
        issues.append(_issue(rule, observation, None, None, "ordered timestamps", None, "timestamp disorder"))
    del dataset_type
    return tuple(issues)


def _required_fields_present(observation: DailyBar | FundNav | FundamentalFact) -> bool:
    if isinstance(observation, DailyBar):
        return (
            observation.open is not None
            and observation.high is not None
            and observation.low is not None
            and observation.close is not None
            and observation.volume is not None
            and observation.turnover is not None
        )
    if isinstance(observation, FundNav):
        return observation.unit_nav is not None
    return observation.unit is not None and observation.currency is not None


def _numeric_range_valid(observation: DailyBar | FundNav | FundamentalFact) -> bool:
    minimum = Decimal("1e-12")
    maximum = Decimal("1e12")
    if isinstance(observation, DailyBar):
        values: tuple[Decimal | None, ...] = (
            observation.open,
            observation.high,
            observation.low,
            observation.close,
            observation.volume,
            observation.turnover,
        )
    elif isinstance(observation, FundNav):
        values = (observation.unit_nav, observation.cumulative_nav)
    else:
        values = (observation.value,)
    return all(value is not None and minimum <= Decimal(value) <= maximum for value in values)


def _date_valid(observation: DailyBar | FundNav | FundamentalFact) -> bool:
    if isinstance(observation, DailyBar):
        return 2020 <= observation.trading_date.year <= 2100
    if isinstance(observation, FundNav):
        return 2020 <= observation.valuation_date.year <= 2100
    return (
        2020 <= observation.reporting_period_start.year <= 2100
        and 2020 <= observation.reporting_period_end.year <= 2100
    )


def _currency_valid(observation: DailyBar | FundNav | FundamentalFact) -> bool:
    currency = _currency(observation)
    if currency is None:
        return True
    return len(currency) == 3 and currency.isalpha()


def _currency(observation: DailyBar | FundNav | FundamentalFact) -> str | None:
    if isinstance(observation, DailyBar):
        return observation.trading_currency
    if isinstance(observation, FundNav):
        return observation.pricing_currency
    return observation.currency


def _unit_valid(observation: DailyBar | FundNav | FundamentalFact) -> bool:
    return not isinstance(observation, FundamentalFact) or bool(observation.unit)


def _lifecycle_valid(observation: DailyBar | FundNav | FundamentalFact) -> bool:
    return bool(observation.canonical_asset_id)


def _mapping_valid(observation: DailyBar | FundNav | FundamentalFact) -> bool:
    return bool(observation.provider and observation.canonical_asset_id)


def _timestamp_order_valid(observation: DailyBar | FundNav | FundamentalFact) -> bool:
    if isinstance(observation, DailyBar):
        return observation.retrieved_at >= observation.provider_available_at
    if isinstance(observation, FundNav):
        return observation.retrieved_at >= observation.provider_available_at
    if isinstance(observation, FundamentalFact):
        return observation.provider_available_at > observation.announcement_at
    return True


def _text(observation: DailyBar | FundNav | FundamentalFact) -> str | None:
    if isinstance(observation, DailyBar):
        return observation.provider or observation.provider_code
    if isinstance(observation, FundNav):
        return observation.provider or observation.provider_code
    return observation.revision_version or observation.provider


def _issue(
    rule: QualityRule,
    observation: DailyBar | FundNav | FundamentalFact,
    _unmatched: object,
    observation_date: date | None,
    expected_condition: str,
    unavailable_dependency: str | None,
    evidence: str,
) -> QualityIssue:
    del _unmatched
    return QualityIssue(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        severity=rule.severity,
        canonical_asset_id=observation.canonical_asset_id,
        observation_date=observation_date,
        field=None,
        observed_value=None,
        expected_condition=expected_condition,
        unavailable_dependency=unavailable_dependency,
        evidence=evidence,
    )


def _counts(issues: tuple[QualityIssue, ...]) -> QualityCounts:
    return QualityCounts(
        valid=sum(issue.severity == "valid" for issue in issues),
        warning=sum(issue.severity == "warning" for issue in issues),
        rejected=sum(issue.severity == "rejected" for issue in issues),
    )


def _evaluate_identity_mapping(
    result: QualityEvaluationResult,
    identity_id: str | None,
) -> QualityEvaluationResult:
    return QualityEvaluationResult(
        quality_status=result.quality_status,
        quality_issues=result.quality_issues,
        identifier=identity_id,
    )


def _now(zone: timezone) -> datetime:
    return datetime.now(tz=zone)
