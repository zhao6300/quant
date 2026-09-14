from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Final

DAILY_BAR_PRECISION: Final[int] = 28
DAILY_BAR_SCALE: Final[int] = 8
FX_PRECISION: Final[int] = 50
FX_SCALE: Final[int] = 24


def aware_utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be aware")
    return value.astimezone(UTC)


def canonical_decimal(
    value: Decimal,
    *,
    precision: int = DAILY_BAR_PRECISION,
    scale: int = DAILY_BAR_SCALE,
    lower_bound: Decimal | None = None,
    upper_bound: Decimal | None = None,
) -> Decimal:
    if not value.is_finite():
        raise ValueError("decimal value must be finite")
    if lower_bound is not None and value < lower_bound:
        raise ValueError("decimal value is below required lower bound")
    if upper_bound is not None and value > upper_bound:
        raise ValueError("decimal value is above required upper bound")

    quantum = Decimal(1).scaleb(-scale)
    with localcontext() as context:
        context.prec = precision + 4
        quantized = value.quantize(quantum, rounding=ROUND_HALF_EVEN)
    if quantized != value or len(quantized.as_tuple().digits) > precision:
        raise ValueError("decimal value exceeds required precision or scale")
    return quantized


def decimal_string(value: Decimal) -> str:
    return str(value)
