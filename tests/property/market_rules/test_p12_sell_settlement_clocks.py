from __future__ import annotations

from datetime import date
from typing import Final

from hypothesis import given, settings
from hypothesis import strategies as st

MARKET_OPTIONS: Final = ("A_SHARE", "HONG_KONG", "UNITED_STATES")
SETTLEMENT_DATES: Final = {
    "A_SHARE": date(2024, 1, 1),
    "HONG_KONG": date(2024, 1, 2),
    "UNITED_STATES": date(2024, 1, 3),
}


@given(
    market=st.sampled_from(MARKET_OPTIONS),
    trade_date=st.dates(),
    settlement_day=st.dates(),
    settlement_kind=st.sampled_from(
        (
            "normal",
            "blacklisted",
            "non_forward",
            "instantaneous",
        )
    ),
)
@settings(max_examples=30, deadline=None)
def test_exact_market_settlement_date(
    market: str,
    trade_date: date,
    settlement_day: date,
    settlement_kind: str,
) -> None:
    assert _settlement_date(market, trade_date, settlement_day, settlement_kind) == settlement_day


def _settlement_date(
    market: str,
    trade_date: date,
    settlement_day: date,
    settlement_kind: str,
) -> date:
    assert market in MARKET_OPTIONS
    return settlement_day
