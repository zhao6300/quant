from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from mmqp.domain.providers import ProviderCategorizedError


def _provenance_id(provider: str, symbol: str, reference: object) -> str:
    return hashlib.sha256(f"{provider}|{symbol}|{reference}".encode()).hexdigest()


def _provider_time(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _currency(value: str) -> str:
    if len(value) != 3 or not value.isalpha():
        raise _invalid_response("currency")
    return value


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise _invalid_response("numeric") from error
    if result.is_finite() and result.is_signed() is False and result > 0:
        return result
    raise _invalid_response("numeric")


def _large_decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise _invalid_response("numeric") from error
    if result.is_finite() and result >= 0:
        return result
    raise _invalid_response("numeric")


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _array_object(value: object) -> list[dict[str, Any]]:
    return value if isinstance(value, list) and all(isinstance(item, dict) for item in value) else []


def _invalid_response(field: str) -> ProviderCategorizedError:
    return ProviderCategorizedError(
        category="invalid_response",
        provider_name="data-source",
        request_category="daily-bar",
        status=502,
        retry="never",
    )


def _stooq_currency(symbol: str) -> str:
    mapping = (
        (".us", "USD"),
        (".hk", "HKD"),
        (".sh", "CNY"),
        (".sz", "CNY"),
    )
    normalized = symbol.lower()
    for suffix, currency in mapping:
        if normalized.endswith(suffix):
            return currency
    raise _invalid_response("currency")


def _exact_item(value: object) -> dict[str, Any]:
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise _invalid_response("payload")
    return value[0]


def _decimal_field(row: dict[str, Any], field: str) -> Decimal:
    if field not in row:
        raise _invalid_response(field)
    return _decimal(row[field])


def _number_field(row: dict[str, Any], field: str) -> Decimal:
    if field not in row:
        raise _invalid_response(field)
    return _large_decimal(row[field])


def _decimal_at(values: dict[str, Any], field: str, index: int) -> Decimal:
    series = values.get(field)
    if not isinstance(series, list) or index >= len(series):
        raise _invalid_response(field)
    return _decimal(series[index])


def _number_at(values: dict[str, Any], field: str, index: int) -> Decimal:
    series = values.get(field)
    if not isinstance(series, list) or index >= len(series):
        raise _invalid_response(field)
    return _large_decimal(series[index])
