from datetime import date, timedelta
from decimal import Decimal

from mmqp.domain.fx import (
    CurrencyConversion,
    FXPolicy,
    FXRate,
    UnavailableCurrencyConversion,
)


def policy_dates(valuation_date: date, policy: FXPolicy) -> tuple[date, ...]:
    if policy.convention == "EXACT_DATE":
        return (valuation_date,)
    return tuple(valuation_date - timedelta(days=offset) for offset in range(5))


def convert(
    value: Decimal,
    source_currency: str,
    rates: tuple[FXRate, ...],
    valuation_date: date,
    policy: FXPolicy,
) -> CurrencyConversion | UnavailableCurrencyConversion:
    if value <= Decimal(0):
        raise ValueError("FX source value must be positive")
    currency = policy.base_currency
    if source_currency == currency:
        return CurrencyConversion(
            source_value=value,
            source_currency=source_currency,
            converted_value=value,
            base_currency=currency,
            rate_version_id=None,
            rate_date=None,
            rate=None,
            provenance_id=None,
        )
    examined = policy_dates(valuation_date, policy)
    applicable = [
        rate
        for rate in rates
        if rate.source_currency == source_currency
        and rate.target_currency == currency
        and rate.rate_date in examined
    ]
    if not applicable:
        return UnavailableCurrencyConversion(
            source_currency=source_currency,
            target_currency=currency,
            valuation_date=valuation_date,
            policy=policy,
            examined_dates=examined,
        )
    selected = max(applicable, key=lambda rate: (rate.rate_date, rate.version_id))
    return CurrencyConversion(
        source_value=value,
        source_currency=source_currency,
        converted_value=value * selected.rate,
        base_currency=currency,
        rate_version_id=selected.version_id,
        rate_date=selected.rate_date,
        rate=selected.rate,
        provenance_id=selected.provenance_id,
    )
