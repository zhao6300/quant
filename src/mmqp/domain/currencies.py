from __future__ import annotations

from dataclasses import dataclass
from re import match
from typing import Final

import pycountry

ISO_CURRENCY_PATTERN: Final = r"^[A-Z]{3}$"


@dataclass(frozen=True, slots=True, kw_only=True)
class CurrencyAmount:
    currency: str
    value: float


def canonical_currency(value: str) -> str:
    normalized = value.upper().strip()
    if match(ISO_CURRENCY_PATTERN, normalized) is None:
        raise ValueError("currency must be a three-letter ISO code")
    if pycountry.currencies.get(alpha_3=normalized) is None:
        raise ValueError("currency is not ISO 4217")
    return normalized
