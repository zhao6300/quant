import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from mmqp.domain.errors import DomainError, ProblemV1

DatasetType = Literal["DAILY_BAR", "FUND_NAV", "FUNDAMENTAL_FACT"]
DATASETS: tuple[DatasetType, ...] = ("DAILY_BAR", "FUND_NAV", "FUNDAMENTAL_FACT")
PRICE_MIN = Decimal("0.00000001")
PRICE_MAX = Decimal("999999999999.99999999")
VOLUME_MIN = Decimal("0")
VOLUME_MAX = Decimal("999999999999999999.99999999")
FACT_VALUE_MIN = Decimal("-1000000000000000000000000")
FACT_VALUE_MAX = Decimal("1000000000000000000000000")


@dataclass(frozen=True, slots=True)
class DailyBar:
    canonical_asset_id: str
    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Decimal
    trading_currency: str
    provider_available_at: datetime
    retrieved_at: datetime
    provider: str
    provider_code: str
    provenance_id: str


@dataclass(frozen=True, slots=True)
class FundNav:
    canonical_asset_id: str
    valuation_date: date
    unit_nav: Decimal
    cumulative_nav: Decimal | None
    pricing_currency: str
    provider_available_at: datetime
    retrieved_at: datetime
    provider: str
    provider_code: str
    provenance_id: str


@dataclass(frozen=True, slots=True)
class FundamentalFact:
    canonical_asset_id: str
    metric_name: str
    value: Decimal
    unit: str
    currency: str | None
    reporting_period_start: date
    reporting_period_end: date
    announcement_at: datetime
    provider_available_at: datetime
    provider: str
    revision_version: str
    provenance_id: str


@dataclass(frozen=True, slots=True)
class DataVersion:
    version_id: str
    revision_id: str
    dataset: DatasetType
    canonical_asset_id: str
    logical_date: date
    logical_key: str
    predecessor_id: str | None
    revision_position: int
    created_at: datetime
    content_id: str
    observation: DailyBar | FundNav | FundamentalFact


@dataclass(frozen=True, slots=True)
class FactExclusion:
    data_version_id: str
    content_id: str
    revision_id: str
    revision_version: str
    available_at: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class FactSelection:
    observation: FundamentalFact | None
    excluded: tuple[FactExclusion, ...]


@dataclass(frozen=True, slots=True)
class IncrementalSegment:
    start_date: date
    end_date: date


class IngestionValidationError(DomainError):
    def __init__(self, fields: list[str] | None = None):
        super().__init__(
            ProblemV1(
                kind="ingestion/record-invalid",
                title="Invalid normalized market observation",
                status=422,
                detail=(
                    None if not fields else f"normalized observation rule violations: {', '.join(fields)}"
                ),
            )
        )
        self.fields = fields


def validate_daily_bar(observation: DailyBar) -> None:
    fields = _base_fields(observation, ("trading_date",))
    for name in ("open", "high", "low", "close"):
        if not _range_value(getattr(observation, name), PRICE_MIN, PRICE_MAX):
            fields.append(f"{name}.range")
    for name in ("volume", "turnover"):
        if not _range_value(getattr(observation, name), VOLUME_MIN, VOLUME_MAX):
            fields.append(f"{name}.range")
    if observation.high < max(observation.open, observation.low, observation.close):
        fields.append("high.relationship")
    if observation.low > min(observation.open, observation.high, observation.close):
        fields.append("low.relationship")
    _raise_fields(fields)


def validate_fund_nav(
    observation: FundNav,
    current_unit_nav: Decimal | None = None,
) -> None:
    fields = _base_fields(observation, ("valuation_date",))
    for name in ("unit_nav", "cumulative_nav"):
        value = getattr(observation, name)
        if value is None or not _range_value(value, PRICE_MIN, PRICE_MAX):
            fields.append(f"{name}.range")
    for value in (observation.unit_nav, observation.cumulative_nav):
        if (
            value is not None
            and observation.cumulative_nav is not None
            and value > observation.cumulative_nav
        ):
            fields.append("cumulative_nav.relationship")
    if (
        current_unit_nav is not None
        and observation.cumulative_nav is not None
        and observation.cumulative_nav < current_unit_nav
    ):
        fields.append("cumulative_nav.relationship")
    _raise_fields(fields)


def validate_fundamental_fact(observation: FundamentalFact) -> None:
    fields = _base_fields(observation)
    if not 1 <= len(observation.metric_name) <= 128:
        fields.append("metric_name.length")
    if not 1 <= len(observation.unit) <= 32:
        fields.append("unit.length")
    if not _range_value(observation.value, FACT_VALUE_MIN, FACT_VALUE_MAX):
        fields.append("value.range")
    if observation.currency is None and _currency_metric(observation.metric_name):
        fields.append("currency.missing")
    if observation.reporting_period_start > observation.reporting_period_end:
        fields.append("reporting_period.relationship")
    _raise_fields(fields)


def canonical_content_id(observation: DailyBar | FundNav | FundamentalFact) -> str:
    return hashlib.sha256(canonical_json(observation).encode("utf-8")).hexdigest()


def canonical_json(observation: DailyBar | FundNav | FundamentalFact) -> str:
    values: tuple[tuple[str, object, str], ...]
    if isinstance(observation, DailyBar):
        values = (
            ("canonical_asset_id", observation.canonical_asset_id, "text"),
            ("trading_date", observation.trading_date.isoformat(), "date"),
            ("open", _decimal_text(observation.open), "decimal"),
            ("high", _decimal_text(observation.high), "decimal"),
            ("low", _decimal_text(observation.low), "decimal"),
            ("close", _decimal_text(observation.close), "decimal"),
            ("volume", _decimal_text(observation.volume), "decimal"),
            ("turnover", _decimal_text(observation.turnover), "decimal"),
            ("trading_currency", observation.trading_currency, "text"),
            ("provider_available_at", _timestamp_value(observation.provider_available_at), "timestamp"),
            ("retrieved_at", _timestamp_value(observation.retrieved_at), "timestamp"),
            ("provider", observation.provider, "text"),
            ("provider_code", observation.provider_code, "text"),
            ("provenance_id", observation.provenance_id, "text"),
        )
    elif isinstance(observation, FundNav):
        values = (
            ("canonical_asset_id", observation.canonical_asset_id, "text"),
            ("valuation_date", observation.valuation_date.isoformat(), "date"),
            ("unit_nav", _decimal_text(observation.unit_nav), "decimal"),
            (
                "cumulative_nav",
                None if observation.cumulative_nav is None else _decimal_text(observation.cumulative_nav),
                "decimal",
            ),
            ("pricing_currency", observation.pricing_currency, "text"),
            ("provider_available_at", _timestamp_value(observation.provider_available_at), "timestamp"),
            ("retrieved_at", _timestamp_value(observation.retrieved_at), "timestamp"),
            ("provider", observation.provider, "text"),
            ("provider_code", observation.provider_code, "text"),
            ("provenance_id", observation.provenance_id, "text"),
        )
    else:
        values = (
            ("canonical_asset_id", observation.canonical_asset_id, "text"),
            ("metric_name", observation.metric_name, "text"),
            ("value", _decimal_text(observation.value), "decimal"),
            ("unit", observation.unit, "text"),
            ("currency", observation.currency, "text"),
            ("reporting_period_start", observation.reporting_period_start.isoformat(), "date"),
            ("reporting_period_end", observation.reporting_period_end.isoformat(), "date"),
            ("announcement_at", _timestamp_value(observation.announcement_at), "timestamp"),
            ("provider_available_at", _timestamp_value(observation.provider_available_at), "timestamp"),
            ("provider", observation.provider, "text"),
            ("revision_version", observation.revision_version, "text"),
            ("provenance_id", observation.provenance_id, "text"),
        )
    return json.dumps(
        [{"field": field, "type": kind, "value": value} for field, value, kind in values],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _base_fields(
    observation: DailyBar | FundNav | FundamentalFact,
    date_fields: tuple[str, ...] = (),
) -> list[str]:
    fields: list[str] = []
    for field_name in ("canonical_asset_id", "provider", "provenance_id"):
        value = getattr(observation, field_name)
        if not isinstance(value, str) or not value.strip():
            fields.append(f"{field_name}.missing")
        elif len(value) > 128:
            fields.append(f"{field_name}.length")
    for field_name in date_fields:
        value = getattr(observation, field_name)
        if not isinstance(value, date) or not 2020 <= value.year <= 2100:
            fields.append(f"{field_name}.range")
    if not isinstance(observation, FundamentalFact):
        for field_name in ("provider_available_at", "retrieved_at"):
            if not _aware(getattr(observation, field_name)):
                fields.append(f"{field_name}.timezone")
        currency = (
            observation.trading_currency
            if isinstance(observation, DailyBar)
            else observation.pricing_currency
        )
        name = "trading_currency" if isinstance(observation, DailyBar) else "pricing_currency"
        if not currency.strip() or len(currency) != 3:
            fields.append(f"{name}.currency")
        if not observation.provider_code.strip() or len(observation.provider_code) > 128:
            fields.append("provider_code.length")
    else:
        for field_name in ("announcement_at", "provider_available_at"):
            if not _aware(getattr(observation, field_name)):
                fields.append(f"{field_name}.timezone")
        if not observation.revision_version.strip() or len(observation.revision_version) > 128:
            fields.append("revision_version.length")
    return fields


def _currency_metric(metric_name: str) -> bool:
    normalized = metric_name.casefold()
    return any(
        normalized == name or normalized.startswith(f"{name}.") or normalized.startswith(f"{name} ")
        for name in ("price", "revenue", "profit", "cash", "cost", "expense")
    )


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.utcoffset() is not None


def _range_value(value: Decimal, minimum: Decimal, maximum: Decimal) -> bool:
    try:
        return minimum <= value <= maximum
    except TypeError:
        return False


def _decimal_text(value: Decimal) -> str:
    if value.is_nan() or value.is_infinite():
        raise IngestionValidationError(["value.range"])
    return f"{value:f}"


def _timestamp_value(value: datetime) -> str:
    if value.tzinfo is None:
        raise IngestionValidationError(["timestamp.timezone"])
    return value.isoformat()


def _raise_fields(fields: list[str]) -> None:
    unique = sorted(set(fields))
    if unique:
        raise IngestionValidationError(unique)
