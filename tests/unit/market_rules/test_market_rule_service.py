from datetime import date
from decimal import Decimal

from mmqp.domain.market_rules import (
    MarketRuleProfile,
)


def _profile(version_id: str, market: str = "A_SHARE", exchange: str = "SSE") -> MarketRuleProfile:
    return MarketRuleProfile(
        version_id=version_id,
        market=market,
        exchange=exchange,
        asset_type="EQUITY",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        trading_lot=100,
        tick_size=Decimal("0.01"),
        price_limit_rule="STATIC_PERCENTAGE_BASE_REFERENCE",
        price_limit_percent=Decimal("0.10"),
        sell_availability_rule="NEXT_OPEN_MARKET_DATE",
        security_settlement_open_dates=2,
        cash_settlement_open_dates=1,
        permitted_session_types=("regular",),
    )
