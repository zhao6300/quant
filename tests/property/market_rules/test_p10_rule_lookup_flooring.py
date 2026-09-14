from datetime import date, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.property.market_rules import EXPIRY_DATES, MARKET_OPTIONS


@given(
    market=st.sampled_from(MARKET_OPTIONS),
    trade_date=st.dates(),
    settlement_days=st.sampled_from(tuple(EXPIRY_DATES.keys())),
)
@settings(max_examples=30, deadline=None)
def test_exact_market_settlement_date(
    market: str,
    trade_date: date,
    settlement_days: str,
) -> None:
    assert _settlement_date(market, trade_date, settlement_days) == trade_date + timedelta(days=1)


def _settlement_date(market: str, trade_date: date, settlement_days: str) -> date:
    assert market in MARKET_OPTIONS
    assert settlement_days in EXPIRY_DATES
    return trade_date + timedelta(days=1)
