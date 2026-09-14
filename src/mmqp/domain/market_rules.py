from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from mmqp.domain.errors import DomainError, ProblemV1

PriceLimitRule = Literal["NONE", "STATIC_PERCENTAGE_BASE_REFERENCE", "PROVIDER_BAND_REQUIRED"]
SellAvailabilityRule = Literal["SAME_MARKET_DATE", "NEXT_OPEN_MARKET_DATE"]
SessionKind = Literal["regular", "non_regular"]
HaltStatus = Literal["ACTIVE", "SUSPENDED", "DELISTED", "UNKNOWN", "UNLISTED"]
TradeSide = Literal["BUY", "SELL"]


@dataclass(frozen=True, slots=True)
class MarketRuleProfile:
    version_id: str
    market: str
    exchange: str
    asset_type: str
    effective_from: date
    effective_to: date | None
    trading_lot: int
    tick_size: Decimal
    price_limit_rule: PriceLimitRule
    price_limit_percent: Decimal | None
    sell_availability_rule: SellAvailabilityRule
    security_settlement_open_dates: int
    cash_settlement_open_dates: int
    permitted_session_types: tuple[SessionKind, ...]


@dataclass(frozen=True, slots=True)
class MarketRuleSelection:
    profile: MarketRuleProfile | None
    matching_profile_ids: tuple[str, ...] = ()
    resolution_status: Literal["resolved", "missing", "ambiguous"] = "resolved"


@dataclass(frozen=True, slots=True)
class SubmittedTrade:
    market: str
    exchange: str
    asset_type: str
    trade_date: date
    side: TradeSide
    requested_quantity: Decimal | int
    requested_price: Decimal
    session_kind: SessionKind
    market_data_price_limit_percent: Decimal | None
    market_data_price_band_percent: Decimal | None
    halt_status: HaltStatus
    reference_price: Decimal | None
    sellable_quantity: Decimal | int


@dataclass(frozen=True, slots=True)
class EvaluatedTrade:
    filled_quantity: Decimal
    valid_quantity: Decimal | None
    valid_price: Decimal | None
    sell_available_date: date | None
    security_settlement_date: date | None
    cash_settlement_date: date | None
    rejection_reason: str | None
    rule_source_version_id: str | None
    matches: tuple[str, ...] = ()


class MarketRuleValidationError(DomainError):
    def __init__(self, fields: list[str] | None = None):
        super().__init__(
            ProblemV1(
                kind="market-rule/profile-invalid",
                title="Invalid market-rule profile",
                status=400,
                detail=None if fields is None else f"market-rule profile invalid: {', '.join(fields)}",
            )
        )
        self.fields = fields


class MarketRuleResolutionError(DomainError):
    def __init__(self, status: int, resolution_status: str, detail: str | None = None):
        super().__init__(
            ProblemV1(
                kind=f"market-rule/profile-{resolution_status}",
                title="Market-rule profile resolution failed",
                status=status,
                detail=detail,
            )
        )
        self.resolution_status = resolution_status
