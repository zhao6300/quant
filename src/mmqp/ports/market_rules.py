from builtins import list as list_type
from datetime import date
from typing import Protocol

from mmqp.domain.market_rules import MarketRuleProfile


class MarketRuleRepository(Protocol):
    def create(self, profile: MarketRuleProfile) -> MarketRuleProfile: ...
    def list(
        self,
        market: str | None = None,
        exchange: str | None = None,
        asset_type: str | None = None,
    ) -> list_type[MarketRuleProfile]: ...
    def select(
        self,
        market: str,
        exchange: str,
        asset_type: str,
        as_of: date,
    ) -> list_type[MarketRuleProfile]: ...
    def close(self) -> None: ...
