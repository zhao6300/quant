from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

AssetOperation = Literal["BUY", "SELL"]
SettlementStatus = Literal["UNSETTLED", "SETTLED"]
ValuationPolicy = Literal["UNAVAILABLE", "LATEST_PRIOR"]
CorporateActionType = Literal[
    "CASH_DIVIDEND",
    "STOCK_SPLIT",
    "STOCK_CONSOLIDATION",
    "RIGHTS_ISSUE",
]


@dataclass(frozen=True, slots=True)
class ManifestPins:
    experiment_id: str
    strategy_version_id: str
    data_snapshot_id: str
    universe_version_id: str
    portfolio_definition_version_id: str
    trading_calendar_version_id: str
    market_rule_profile_version_id: str
    fx_policy_version_id: str
    fx_rate_version_id: str | None
    corporate_action_version_id: str | None
    transaction_cost_model_version_id: str

    def validate(self) -> None:
        required = {
            "experiment_id": self.experiment_id,
            "strategy_version_id": self.strategy_version_id,
            "data_snapshot_id": self.data_snapshot_id,
            "universe_version_id": self.universe_version_id,
            "portfolio_definition_version_id": self.portfolio_definition_version_id,
            "trading_calendar_version_id": self.trading_calendar_version_id,
            "market_rule_profile_version_id": self.market_rule_profile_version_id,
            "fx_policy_version_id": self.fx_policy_version_id,
            "transaction_cost_model_version_id": self.transaction_cost_model_version_id,
        }
        missing = sorted(key for key, value in required.items() if not value.strip())
        if missing:
            raise ValueError(f"missing manifest pins: {', '.join(missing)}")


@dataclass(frozen=True, slots=True)
class StrategyInput:
    asset_id: str
    available_at: datetime
    version_id: str


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    decision_id: str
    decision_at: datetime
    targets: tuple[tuple[str, Decimal], ...]
    inputs: tuple[StrategyInput, ...] = ()

    def validate(self) -> None:
        ids = [asset_id for asset_id, _weight in self.targets]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate target asset")
        total = sum((weight for _asset_id, weight in self.targets), Decimal(0))
        if any(weight < Decimal(0) for _asset_id, weight in self.targets) or total != Decimal(1):
            raise ValueError("target weights must be non-negative and sum to one")


@dataclass(frozen=True, slots=True)
class Position:
    quantity: Decimal = Decimal(0)
    cost_basis: Decimal = Decimal(0)
    sellable_quantity: Decimal = Decimal(0)


@dataclass(slots=True)
class LedgerState:
    cash: Decimal = Decimal(0)
    unsettled_cash: Decimal = Decimal(0)
    positions: dict[str, Position] = field(default_factory=dict)
    fills: list[TradeFill] = field(default_factory=list)
    corporate_actions: list[CorporateAction] = field(default_factory=list)
    valuations: list[Valuation] = field(default_factory=list)
    unavailable_values: list[UnavailableValue] = field(default_factory=list)
    bias_warnings: list[str] = field(default_factory=list)

    def position(self, asset_id: str) -> Position:
        return self.positions.get(asset_id, Position())

    def assert_invariant(self) -> None:
        if self.cash < Decimal(0) or self.unsettled_cash < Decimal(0):
            raise ValueError("cash ledger invariant violated")
        if any(position.quantity < Decimal(0) for position in self.positions.values()):
            raise ValueError("security quantity invariant violated")


@dataclass(frozen=True, slots=True)
class MarketRuleProfile:
    version_id: str
    market: str
    exchange: str
    asset_type: str
    effective_from: date
    effective_to: date | None = None
    trading_lot: int = 1
    tick_size: Decimal = Decimal("0.01")
    sell_availability_rule: Literal["SAME_MARKET_DATE", "NEXT_OPEN_MARKET_DATE"] = "SAME_MARKET_DATE"
    security_settlement_open_dates: int = 1
    cash_settlement_open_dates: int = 1
    price_limit_percent: Decimal | None = None

    def active(self, trade_date: date) -> bool:
        return self.effective_from <= trade_date and (
            self.effective_to is None or trade_date <= self.effective_to
        )

    def validate(self) -> None:
        if self.trading_lot < 1 or self.trading_lot > 1_000_000_000:
            raise ValueError("trading lot is out of range")
        if self.tick_size <= Decimal(0) or self.tick_size > Decimal(1_000_000_000):
            raise ValueError("tick size is out of range")
        if self.security_settlement_open_dates < 0 or self.cash_settlement_open_dates < 0:
            raise ValueError("settlement open dates must be non-negative")


@dataclass(frozen=True, slots=True)
class TradingCalendarDay:
    market: str
    exchange: str
    day: date
    open: bool
    regular_sessions: tuple[tuple[datetime, datetime], ...] = ()


@dataclass(frozen=True, slots=True)
class TradingCalendar:
    version_id: str
    market: str
    exchange: str
    timezone: str
    effective_from: date
    effective_to: date | None
    days: tuple[TradingCalendarDay, ...]

    def active(self, day: date) -> bool:
        return self.effective_from <= day and (self.effective_to is None or day <= self.effective_to)

    def day(self, day: date) -> TradingCalendarDay:
        for candidate in self.days:
            if candidate.day == day:
                return candidate
        raise ValueError(f"calendar day {day.isoformat()} is missing")

    def open_days(self, count: int, start: date) -> tuple[date, ...]:
        current = start
        found: list[date] = []
        for _ in range(30):
            if self.active(current) and self.day(current).open:
                found.append(current)
                if len(found) == count:
                    return tuple(found)
            current += timedelta(days=1)
        raise ValueError("calendar does not contain enough open days")


@dataclass(frozen=True, slots=True)
class CostRule:
    version_id: str
    effective_from: date
    effective_to: date | None = None
    commission_rate: Decimal = Decimal(0)
    tax_rate: Decimal = Decimal(0)
    platform_rate: Decimal = Decimal(0)
    slippage_rate: Decimal = Decimal(0)
    minimum_cost: Decimal = Decimal(0)

    def active(self, trade_date: date) -> bool:
        return self.effective_from <= trade_date and (
            self.effective_to is None or trade_date <= self.effective_to
        )


@dataclass(frozen=True, slots=True)
class TradeRequest:
    request_id: str
    decision_id: str
    asset_id: str
    market: str
    exchange: str
    asset_type: str
    side: AssetOperation
    requested_quantity: Decimal
    requested_price: Decimal
    currency: str
    decision_at: datetime
    inputs: tuple[StrategyInput, ...] = ()
    price_limit_percent: Decimal | None = None
    halt_status: Literal["ACTIVE", "SUSPENDED", "DELISTED", "UNKNOWN"] = "ACTIVE"
    reference_price: Decimal | None = None
    sellable_quantity: Decimal | None = None
    vendor_data_band_percent: Decimal | None = None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def valuations_for(
    prices: Sequence[PriceBar],
    quantities: Mapping[str, Decimal],
    policy: ValuationPolicy = "LATEST_PRIOR",
) -> tuple[Valuation, ...]:
    if policy == "UNAVAILABLE":
        return ()
    valuations: list[Valuation] = []
    for asset_id in sorted(set(quantities) & {bar.asset_id for bar in prices}):
        bars = sorted((bar for bar in prices if bar.asset_id == asset_id), key=lambda bar: bar.source_date)
        quantity = quantities[asset_id]
        if bars and quantity >= Decimal(0):
            bar = bars[-1]
            valuations.append(
                Valuation(
                    asset_id=asset_id,
                    value_date=bar.source_date,
                    source_market_date=bar.source_date,
                    price=bar.close,
                    fx_rate_date=None,
                    fx_rate_version_id=None,
                    local_value=bar.close * quantity,
                    base_value=bar.close * quantity,
                )
            )
    return tuple(valuations)


@dataclass(frozen=True, slots=True)
class TradeFill:
    fill_id: str
    request_id: str
    asset_id: str
    side: AssetOperation
    requested_quantity: Decimal
    valid_lot_quantity: Decimal
    filled_quantity: Decimal
    local_execution_price: Decimal
    trading_currency: str
    base_currency: str
    fx_rate_version_id: str | None
    gross_value: Decimal
    base_value: Decimal
    cost_components: tuple[tuple[str, Decimal], ...]
    total_cost: Decimal
    trade_timestamp: datetime
    source_market_date: date
    sell_available_date: date | None
    settlement_date: date
    terminal_status: Literal["FILLED", "ZERO", "REJECTED"]
    reason: str | None


@dataclass(frozen=True, slots=True)
class CorporateAction:
    event_id: str
    asset_id: str
    action_type: CorporateActionType
    effective_date: date
    cash_amount: Decimal = Decimal(0)
    ratio: Decimal = Decimal(1)


@dataclass(frozen=True, slots=True)
class Valuation:
    asset_id: str
    value_date: date
    source_market_date: date
    price: Decimal
    fx_rate_date: date | None
    fx_rate_version_id: str | None
    local_value: Decimal
    base_value: Decimal


@dataclass(frozen=True, slots=True)
class UnavailableValue:
    asset_id: str
    value_date: date
    reason: str


@dataclass(frozen=True, slots=True)
class BacktestResult:
    pins: ManifestPins
    holdings: tuple[tuple[str, Decimal], ...]
    settled_cash: Decimal
    unsettled_cash: Decimal
    trades: tuple[TradeFill, ...]
    corporate_actions: tuple[CorporateAction, ...]
    valuations: tuple[Valuation, ...]
    unavailable_values: tuple[UnavailableValue, ...]
    transaction_cost_series: tuple[tuple[str, Decimal], ...]
    bias_warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TradePlan:
    asset_id: str
    decision_id: str
    requested: Decimal
    available: Decimal
    price: Decimal
    side: AssetOperation = "BUY"


@dataclass(frozen=True, slots=True)
class PriceBar:
    asset_id: str
    market: str
    source_date: date
    close: Decimal


@dataclass(frozen=True, slots=True)
class SchedulePlan:
    pins: ManifestPins
    decisions: tuple[StrategyDecision, ...]
    trades: tuple[TradePlan, ...]
    corporate_actions: tuple[CorporateAction, ...]
    calendar: TradingCalendar
    market_rules: tuple[MarketRuleProfile, ...]
    cost_rules: tuple[CostRule, ...]


@dataclass(frozen=True, slots=True)
class BacktestPlan:
    pins: ManifestPins
    requests: tuple[TradeRequest, ...]
    prices: tuple[PriceBar, ...]
    calendars: tuple[TradingCalendar, ...]
    market_rules: tuple[MarketRuleProfile, ...]
    cost_rules: tuple[CostRule, ...]
    initial_cash: Decimal = Decimal(0)
    initial_positions: tuple[tuple[str, Decimal], ...] = ()
    valuation_policy: ValuationPolicy = "LATEST_PRIOR"
    corporate_actions: tuple[CorporateAction, ...] = ()

    def validate(self) -> None:
        self.pins.validate()
        if not self.requests:
            raise ValueError("backtest plan has no trade requests")
        if not self.calendars:
            raise ValueError("backtest plan has no trading calendars")
        if not self.market_rules:
            raise ValueError("backtest plan has no market rules")
        if not self.cost_rules:
            raise ValueError("backtest plan has no cost rules")
        self._validate_requests()
        self._validate_prices()

    def _validate_requests(self) -> None:
        seen: set[tuple[str, date]] = set()
        for request in self.requests:
            request_id = request.request_id.strip()
            if not request_id:
                raise ValueError("trade request id is missing")
            if request.requested_quantity <= Decimal(0):
                raise ValueError("requested quantity must be positive")
            if request.requested_price < Decimal(0):
                raise ValueError("requested price must be non-negative")
            if any(
                _aware(input.available_at) > _aware(request.decision_at)
                for input in request.inputs
            ):
                raise ValueError("strategy input is visible after its decision timestamp")
            key = (request.asset_id, request.decision_at.date())
            if key in seen:
                raise ValueError("more than one decision per asset on a market date")
            seen.add(key)

    def _validate_prices(self) -> None:
        for price in self.prices:
            if price.close < Decimal(0):
                raise ValueError("price close must be non-negative")


@dataclass(frozen=True, slots=True)
class ResolvedRequest:
    request: TradeRequest
    calendar: TradingCalendar
    market_rule: MarketRuleProfile
    cost_rule: CostRule


@dataclass(frozen=True, slots=True)
class ScheduledTrade:
    request: TradeRequest
    execution_at: datetime
    market_date: date


@dataclass(frozen=True, slots=True)
class TradingPlan:
    pins: ManifestPins
    trades: tuple[ScheduledTrade, ...]


def quantity_for_lots(quantity: Decimal, trading_lot: int, side: AssetOperation) -> Decimal:
    if trading_lot <= 0 or quantity < Decimal(0):
        return Decimal(0)
    magnitude = abs(quantity)
    lots = int(magnitude // Decimal(trading_lot))
    return Decimal(lots * trading_lot) if side == "SELL" else Decimal(lots * trading_lot)


def valid_lot_quantity(requested_quantity: Decimal, trading_lot: int, side: AssetOperation) -> Decimal:
    if trading_lot <= 0 or requested_quantity < Decimal(0):
        return Decimal(0)
    magnitude = abs(requested_quantity)
    lots = int(magnitude // Decimal(trading_lot))
    return Decimal(lots * trading_lot) if side == "SELL" else Decimal(lots * trading_lot)


def price_for_ticks(price: Decimal, tick_size: Decimal) -> Decimal:
    if tick_size <= Decimal(0) or price < Decimal(0):
        return Decimal(0)
    return Decimal(int(price // tick_size)) * tick_size


def trade_cost(gross_value: Decimal, cost_rule: CostRule) -> tuple[tuple[str, Decimal], ...]:
    if gross_value < Decimal(0):
        return ()
    cost = [
        ("commission", abs(gross_value) * cost_rule.commission_rate),
        ("tax", abs(gross_value) * cost_rule.tax_rate),
        ("platform", abs(gross_value) * cost_rule.platform_rate),
        ("slippage", abs(gross_value) * cost_rule.slippage_rate),
    ]
    total = sum((component for _name, component in cost), Decimal(0))
    if total < cost_rule.minimum_cost:
        if cost:
            cost[0] = (cost[0][0], cost[0][1] + (cost_rule.minimum_cost - total))
        else:
            cost.append(("minimum", cost_rule.minimum_cost))
    components = tuple(cost)
    return components


def total_cost(components: tuple[tuple[str, Decimal], ...]) -> Decimal:
    return sum((amount for _name, amount in components), Decimal(0))


def max_affordable_lots(
    price: Decimal,
    trading_lot: int,
    cash: Decimal,
    components: tuple[tuple[str, Decimal], ...],
) -> int:
    if trading_lot <= 0 or price <= Decimal(0):
        return 0
    fixed = Decimal(total_cost(components))
    if fixed > cash:
        return 0
    remaining = cash - fixed
    return int(remaining // (Decimal(trading_lot) * price))


def settlefilled_trades(state: LedgerState, settlement_date: date) -> None:
    unpaid = Decimal(0)
    for fill in state.fills:
        if fill.settlement_date <= settlement_date:
            amount = fill.base_value + fill.total_cost
            if fill.side == "SELL":
                amount = -amount
            state.unsettled_cash -= amount
            if fill.side == "SELL":
                state.cash += amount
            else:
                state.cash -= amount
        else:
            unpaid += amount if fill.side == "SELL" else -amount
    state.unsettled_cash = unpaid


def next_regular_session(calendar: TradingCalendar, after: datetime) -> tuple[datetime, date] | None:
    zone = ZoneInfo(calendar.timezone)
    aware_after = after if after.tzinfo is not None else after.replace(tzinfo=UTC)
    for day_record in sorted(calendar.days, key=lambda item: item.day):
        if not calendar.active(day_record.day) or not day_record.open:
            continue
        for start, _end in day_record.regular_sessions:
            local_start = start.replace(tzinfo=zone)
            if local_start > aware_after:
                return local_start, day_record.day
    return None


def session_start_for(
    calendar: TradingCalendar,
    market_rule: MarketRuleProfile,
    request: TradeRequest,
) -> tuple[datetime, date]:
    if market_rule.active(request.decision_at.date()) is False:
        raise ValueError(f"market rule {market_rule} not active on {request.decision_at.date().isoformat()}")
    if calendar.active(request.decision_at.date()) is False:
        raise ValueError(f"calendar {calendar} not active on {request.decision_at.date().isoformat()}")
    candidate = next_regular_session(
        calendar,
        request.decision_at.astimezone(ZoneInfo(calendar.timezone)),
    )
    if candidate is None:
        raise ValueError("no regular session is available after the decision timestamp")
    return candidate


def market_rule_by_id(rules: Sequence[MarketRuleProfile], market_rule_id: str) -> MarketRuleProfile:
    matches: list[MarketRuleProfile] = [rule for rule in rules if rule.version_id == market_rule_id]
    if not matches:
        raise ValueError(f"market rule {market_rule_id} is missing")
    if len(matches) > 1:
        raise ValueError(f"market rule {market_rule_id} is ambiguous")
    return matches[0]


def cost_rule_by_id(rules: Sequence[CostRule], rule_id: str) -> CostRule:
    matches: list[CostRule] = [rule for rule in rules if rule.version_id == rule_id]
    if not matches:
        raise ValueError(f"cost rule {rule_id} is missing")
    if len(matches) > 1:
        raise ValueError(f"cost rule {rule_id} is ambiguous")
    return matches[0]


def _resolve_rule_by_market(
    rules: Sequence[MarketRuleProfile],
    market: str,
    exchange: str,
    asset_type: str,
) -> MarketRuleProfile:
    matches = [
        rule
        for rule in rules
        if rule.market == market
        and rule.exchange == exchange
        and rule.asset_type == asset_type
    ]
    if not matches:
        raise ValueError(
            "missing market rule for "
            f"market={market} exchange={exchange} asset_type={asset_type}"
        )
    if len(matches) > 1:
        ids = sorted(rule.version_id for rule in matches)
        raise ValueError("ambiguous market rules: " + ", ".join(ids))
    return matches[0]


def _resolve_calendar(
    calendars: Sequence[TradingCalendar],
    market: str,
    exchange: str,
) -> TradingCalendar:
    matches = [
        calendar
        for calendar in calendars
        if calendar.market == market and calendar.exchange == exchange
    ]
    if not matches:
        raise ValueError(f"missing trading calendar for market={market} exchange={exchange}")
    if len(matches) > 1:
        ids = sorted(calendar.version_id for calendar in matches)
        raise ValueError("ambiguous trading calendars: " + ", ".join(ids))
    return matches[0]


def _resolve_cost_rules(cost_rules: Sequence[CostRule]) -> CostRule:
    if not cost_rules:
        raise ValueError("missing cost rule")
    if len(cost_rules) > 1:
        ids = sorted(rule.version_id for rule in cost_rules)
        raise ValueError("ambiguous cost rules: " + ", ".join(ids))
    return cost_rules[0]


def resolve_requests(plan: BacktestPlan) -> tuple[ResolvedRequest, ...]:
    plan.validate()
    resolved: list[ResolvedRequest] = []
    cost_rule = _resolve_cost_rules(plan.cost_rules)
    for request in plan.requests:
        calendar = _resolve_calendar(
            plan.calendars,
            request.market,
            request.exchange,
        )
        market_rule = _resolve_rule_by_market(
            plan.market_rules,
            request.market,
            request.exchange,
            request.asset_type,
        )
        resolved.append(
            ResolvedRequest(
                request=request,
                calendar=calendar,
                market_rule=market_rule,
                cost_rule=cost_rule,
            )
        )
    resolved.sort(
        key=lambda item: (
            item.request.request_id,
            item.request.asset_id,
        )
    )
    return tuple(resolved)


def schedule_requests(plan: BacktestPlan) -> TradingPlan:
    resolved = resolve_requests(plan)
    trades: list[ScheduledTrade] = []
    for item in resolved:
        market_rule = item.market_rule
        if not market_rule.active(item.request.decision_at.date()):
            raise ValueError(
                f"market rule {market_rule.version_id} is not active on "
                f"{item.request.decision_at.date().isoformat()}"
            )
        start, market_date = session_start_for(
            item.calendar,
            market_rule,
            item.request,
        )
        trades.append(
            ScheduledTrade(
                request=item.request,
                execution_at=start,
                market_date=market_date,
            )
        )
    trades.sort(
        key=lambda trade: (
            trade.execution_at,
            trade.request.asset_id,
            trade.request.request_id,
        )
    )
    return TradingPlan(pins=plan.pins, trades=tuple(trades))


def _next_settlement_date(
    calendar: TradingCalendar,
    trade_date: date,
    settlement_open_dates: int,
) -> date:
    if settlement_open_dates < 0:
        raise ValueError("settlement open dates cannot be negative")
    current = trade_date
    for _ in range(settlement_open_dates):
        current += timedelta(days=1)
        if not any(day.day == current and day.open for day in calendar.days):
            open_days = sorted(day.day for day in calendar.days if day.open and day.day > current)
            current = open_days[0] if open_days else current
    return current


def execute_trades(plan: BacktestPlan) -> tuple[tuple[TradeFill, ...], Decimal, Decimal, dict[str, Position]]:
    scheduled = schedule_requests(plan)
    cash = plan.initial_cash
    unsettled_cash = Decimal(0)
    positions = {
        asset_id: Position(quantity=quantity, cost_basis=quantity, sellable_quantity=quantity)
        for asset_id, quantity in plan.initial_positions
    }
    fills: list[TradeFill] = []

    for scheduled_trade in scheduled.trades:
        request = scheduled_trade.request
        market_rule = _resolve_rule_by_market(
            plan.market_rules,
            request.market,
            request.exchange,
            request.asset_type,
        )
        calendar = _resolve_calendar(plan.calendars, request.market, request.exchange)
        cost_rule = _resolve_cost_rules(plan.cost_rules)
        settlement_date = _next_settlement_date(
            calendar,
            scheduled_trade.market_date,
            market_rule.cash_settlement_open_dates,
        )

        valid_lot_quantity = Decimal(
            int(request.requested_quantity // Decimal(market_rule.trading_lot))
        ) * Decimal(market_rule.trading_lot)

        blocked = request.halt_status != "ACTIVE"
        price_limited = (
            request.price_limit_percent is not None
            and request.reference_price is not None
            and (request.requested_price - request.reference_price).copy_abs()
            > request.reference_price * request.price_limit_percent / Decimal(100)
        )
        excess_sell = (
            request.side == "SELL"
            and valid_lot_quantity > positions.get(request.asset_id, Position()).sellable_quantity
        )
        if blocked or price_limited or excess_sell:
            fills.append(
                TradeFill(
                    fill_id=f"{request.request_id}-zero",
                    request_id=request.request_id,
                    asset_id=request.asset_id,
                    side=request.side,
                    requested_quantity=request.requested_quantity,
                    valid_lot_quantity=valid_lot_quantity,
                    filled_quantity=Decimal(0),
                    local_execution_price=request.requested_price,
                    trading_currency=request.currency,
                    base_currency=request.currency,
                    fx_rate_version_id=None,
                    gross_value=Decimal(0),
                    base_value=Decimal(0),
                    cost_components=(),
                    total_cost=Decimal(0),
                    trade_timestamp=scheduled_trade.execution_at,
                    source_market_date=scheduled_trade.market_date,
                    sell_available_date=None,
                    settlement_date=settlement_date,
                    terminal_status="ZERO",
                    reason="halt, price limit, or excess sell",
                )
            )
            continue

        requested_gross_value = valid_lot_quantity * request.requested_price
        if request.side == "BUY":
            requested_cost_components = trade_cost(requested_gross_value, cost_rule)
            affordable_lots = max_affordable_lots(
                price=request.requested_price,
                trading_lot=market_rule.trading_lot,
                cash=cash,
                components=requested_cost_components,
            )
            affordable_quantity = Decimal(affordable_lots * market_rule.trading_lot)
            valid_lot_quantity = min(valid_lot_quantity, affordable_quantity)

        if request.side == "SELL":
            sellable_quantity = positions.get(request.asset_id, Position()).sellable_quantity
            valid_lot_quantity = min(valid_lot_quantity, sellable_quantity)

        gross_value = valid_lot_quantity * request.requested_price
        cost_components = trade_cost(gross_value, cost_rule)
        total_cost_value = Decimal(sum((component for _, component in cost_components), Decimal(0)))
        fills.append(
            TradeFill(
                fill_id=request.request_id,
                request_id=request.request_id,
                asset_id=request.asset_id,
                side=request.side,
                requested_quantity=request.requested_quantity,
                valid_lot_quantity=valid_lot_quantity,
                filled_quantity=valid_lot_quantity,
                local_execution_price=request.requested_price,
                trading_currency=request.currency,
                base_currency=request.currency,
                fx_rate_version_id=None,
                gross_value=gross_value,
                base_value=gross_value,
                cost_components=cost_components,
                total_cost=total_cost_value,
                trade_timestamp=scheduled_trade.execution_at,
                source_market_date=scheduled_trade.market_date,
                sell_available_date=settlement_date,
                settlement_date=settlement_date,
                terminal_status="FILLED",
                reason=None,
            )
        )
        if request.side == "BUY":
            cash -= gross_value + total_cost_value
        else:
            cash += gross_value - total_cost_value

        position = positions.setdefault(request.asset_id, Position())
        if request.side == "BUY":
            position = Position(
                quantity=position.quantity + valid_lot_quantity,
                cost_basis=position.cost_basis,
                sellable_quantity=position.quantity + valid_lot_quantity,
            )
        else:
            position = Position(
                quantity=position.quantity - valid_lot_quantity,
                cost_basis=position.cost_basis,
                sellable_quantity=position.quantity - valid_lot_quantity,
            )
        positions[request.asset_id] = position

    return tuple(fills), cash, unsettled_cash, positions


def run_backtest(plan: BacktestPlan) -> BacktestResult:
    plan.validate()
    fills, cash, unsettled_cash, positions = execute_trades(plan)
    holdings = tuple(
        (asset_id, position.quantity)
        for asset_id, position in sorted(positions.items())
        if position.quantity != Decimal(0)
    )
    transaction_cost_series = tuple(
        (fill.asset_id, fill.total_cost)
        for fill in sorted(fills, key=lambda fill: (fill.trade_timestamp, fill.asset_id))
    )
    valuations = tuple(
        Valuation(
            asset_id=asset_id,
            value_date=price.source_date,
            source_market_date=price.source_date,
            price=price.close,
            fx_rate_date=None,
            fx_rate_version_id=None,
            local_value=price.close * quantity,
            base_value=price.close * quantity,
        )
        for asset_id, quantity in holdings
        if (
            prices := sorted(
                (bar for bar in plan.prices if bar.asset_id == asset_id),
                key=lambda bar: bar.source_date,
            )
        )
        for price in (prices[-1],)
    )
    valuations = valuations if plan.valuation_policy == "LATEST_PRIOR" else ()
    unavailable_values = (
        tuple(
            UnavailableValue(
                asset_id=asset_id,
                value_date=price.source_date,
                reason="valuation policy is unavailable",
            )
            for asset_id, _quantity in holdings
            for price in (
                sorted(
                    (bar for bar in plan.prices if bar.asset_id == asset_id),
                    key=lambda bar: bar.source_date,
                )[-1],
            )
        )
        if plan.valuation_policy == "UNAVAILABLE"
        else ()
    )
    return BacktestResult(
        pins=plan.pins,
        holdings=holdings,
        settled_cash=cash,
        unsettled_cash=unsettled_cash,
        trades=fills,
        corporate_actions=plan.corporate_actions,
        valuations=valuations,
        unavailable_values=unavailable_values,
        transaction_cost_series=transaction_cost_series,
        bias_warnings=(),
    )
