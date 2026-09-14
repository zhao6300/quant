from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from mmqp.domain.errors import DomainError, ProblemV1

FXPolicyConvention = Literal["EXACT_DATE", "LATEST_PRIOR_FALLBACK"]
FX_POLICIES: tuple[FXPolicyConvention, ...] = ("EXACT_DATE", "LATEST_PRIOR_FALLBACK")
MIN_RATE = Decimal("1e-12")
MAX_RATE = Decimal("1e12")


@dataclass(frozen=True, slots=True)
class DataProvenance:
    provenance_id: str
    source: str
    retrieval_path: str


@dataclass(frozen=True, slots=True)
class FXRate:
    version_id: str
    source_currency: str
    target_currency: str
    rate_date: date
    rate: Decimal
    provider: str
    provider_pair: str
    retrieved_at: datetime
    provenance_id: str
    data_version_id: str
    direct_source_version_id: str | None = None


@dataclass(frozen=True, slots=True)
class FXPolicy:
    base_currency: str
    convention: FXPolicyConvention


@dataclass(frozen=True, slots=True)
class CurrencyConversion:
    source_value: Decimal
    source_currency: str
    converted_value: Decimal
    base_currency: str
    rate_version_id: str | None
    rate_date: date | None
    rate: Decimal | None
    provenance_id: str | None


@dataclass(frozen=True, slots=True)
class UnavailableCurrencyConversion:
    source_currency: str
    target_currency: str
    valuation_date: date
    policy: FXPolicy
    examined_dates: tuple[date, ...]


class FXValidationError(DomainError):
    def __init__(self, fields: list[str] | None = None):
        super().__init__(
            ProblemV1(
                kind="fx/rate-invalid",
                title="Invalid FX rate",
                status=400,
                detail=None if fields is None else f"FX rate invalid: {', '.join(fields)}",
            )
        )
        self.fields = fields


class FXPolicyError(DomainError):
    def __init__(self, fields: list[str]):
        super().__init__(
            ProblemV1(
                kind="fx/policy-invalid",
                title="FX policy invalid",
                status=400,
                detail=f"FX policy invalid: {', '.join(fields)}",
            )
        )
        self.fields = fields


def validate_policy(policy: FXPolicy) -> None:
    errors: list[str] = []
    if len(policy.base_currency) != 3 or not policy.base_currency.isalpha():
        errors.append("base_currency")
    if policy.convention not in FX_POLICIES:
        errors.append("convention")
    if errors:
        raise FXPolicyError(errors)


def validate_rate(rate: FXRate) -> None:
    errors: list[str] = []
    if not rate.version_id.strip():
        errors.append("version_id")
    if len(rate.source_currency) != 3 or not rate.source_currency.isalpha():
        errors.append("source_currency")
    if len(rate.target_currency) != 3 or not rate.target_currency.isalpha():
        errors.append("target_currency")
    if rate.source_currency == rate.target_currency:
        errors.append("currency_pair")
    if not 2020 <= rate.rate_date.year <= 2100:
        errors.append("rate_date")
    if rate.rate < MIN_RATE or rate.rate > MAX_RATE:
        errors.append("rate")
    if not rate.provider.strip() or len(rate.provider) > 128:
        errors.append("provider")
    if not rate.provider_pair.strip() or len(rate.provider_pair) > 128:
        errors.append("provider_pair")
    if rate.retrieved_at.tzinfo is None:
        errors.append("retrieved_at")
    if not rate.provenance_id.strip() or len(rate.provenance_id) > 128:
        errors.append("provenance_id")
    if not rate.data_version_id.strip() or len(rate.data_version_id) > 128:
        errors.append("data_version_id")
    if errors:
        raise FXValidationError(errors)


def inverse_rate(rate: FXRate, version_id: str) -> FXRate:
    with_decimal = Decimal(1) / rate.rate
    inverse = FXRate(
        version_id=version_id,
        source_currency=rate.target_currency,
        target_currency=rate.source_currency,
        rate_date=rate.rate_date,
        rate=with_decimal,
        provider=rate.provider,
        provider_pair=f"{rate.provider_pair}-INVERSE",
        retrieved_at=rate.retrieved_at,
        provenance_id=rate.provenance_id,
        data_version_id=rate.data_version_id,
        direct_source_version_id=rate.version_id,
    )
    validate_rate(inverse)
    return inverse
