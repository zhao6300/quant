from datetime import date
from decimal import Decimal

from mmqp.domain.market_rules import (
    MarketRuleProfile,
    MarketRuleSelection,
    MarketRuleValidationError,
)
from mmqp.ports.market_rules import MarketRuleRepository

MARKET_TIMEZONES = {
    "A_SHARE": "Asia/Shanghai",
    "HONG_KONG": "Asia/Hong_Kong",
    "UNITED_STATES": "America/New_York",
}


class MarketRuleService:
    def __init__(self, repository: MarketRuleRepository | None = None):
        self._repository = repository

    def register(self, profile: MarketRuleProfile) -> MarketRuleProfile:
        MarketRuleService.validate(profile)
        owned_repository = self._repository
        if owned_repository is None:
            return profile
        return owned_repository.create(profile)

    def list(
        self,
        market: str | None = None,
        exchange: str | None = None,
        asset_type: str | None = None,
    ) -> list[MarketRuleProfile]:
        owned_repository = self._repository
        if owned_repository is None:
            return []
        return owned_repository.list(market, exchange, asset_type)

    def resolve(
        self,
        market: str,
        exchange: str,
        asset_type: str,
        as_of: date,
    ) -> MarketRuleSelection:
        owned_repository = self._repository
        if owned_repository is None:
            return MarketRuleSelection(
                profile=None,
                matching_profile_ids=(),
                resolution_status="missing",
            )
        profiles = owned_repository.select(market, exchange, asset_type, as_of)
        matches = tuple(profile.version_id for profile in profiles)
        if not profiles:
            return MarketRuleSelection(
                profile=None,
                matching_profile_ids=(),
                resolution_status="missing",
            )
        if len(profiles) != 1:
            return MarketRuleSelection(
                profile=None,
                matching_profile_ids=matches,
                resolution_status="ambiguous",
            )
        return MarketRuleSelection(profile=profiles[0], matching_profile_ids=matches)

    @staticmethod
    def validate(profile: MarketRuleProfile) -> None:
        errors: list[str] = []
        if not profile.version_id.strip():
            errors.append("version_id")
        if profile.market not in MARKET_TIMEZONES:
            errors.append("market")
        if not profile.exchange.strip():
            errors.append("exchange")
        if not profile.asset_type.strip():
            errors.append("asset_type")
        if profile.effective_to is not None and profile.effective_to < profile.effective_from:
            errors.append("effective_to")
        if profile.trading_lot < 1 or profile.trading_lot > 1_000_000_000:
            errors.append("trading_lot")
        if profile.tick_size <= Decimal("0") or profile.tick_size > Decimal("1000000000"):
            errors.append("tick_size")
        if profile.price_limit_rule not in {
            "NONE",
            "STATIC_PERCENTAGE_BASE_REFERENCE",
            "PROVIDER_BAND_REQUIRED",
        }:
            errors.append("price_limit_rule")
        if profile.price_limit_rule == "STATIC_PERCENTAGE_BASE_REFERENCE" and (
            profile.price_limit_percent is None or profile.price_limit_percent <= Decimal("0")
        ):
            errors.append("price_limit_percent")
        if (
            profile.price_limit_rule != "STATIC_PERCENTAGE_BASE_REFERENCE"
            and profile.price_limit_percent is not None
        ):
            errors.append("price_limit_percent")
        if profile.sell_availability_rule not in {"SAME_MARKET_DATE", "NEXT_OPEN_MARKET_DATE"}:
            errors.append("sell_availability_rule")
        if profile.security_settlement_open_dates < 0 or profile.security_settlement_open_dates > 8:
            errors.append("security_settlement_open_dates")
        if profile.cash_settlement_open_dates < 0 or profile.cash_settlement_open_dates > 8:
            errors.append("cash_settlement_open_dates")
        if not 1 <= len(profile.permitted_session_types) <= 8:
            errors.append("permitted_session_types")
        if any(session not in {"regular", "non_regular"} for session in profile.permitted_session_types):
            errors.append("permitted_session_types")
        if errors:
            raise MarketRuleValidationError(fields=errors)
