from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import date, timedelta
from decimal import Decimal

from mmqp.domain.calendars import TradingCalendarVersion
from mmqp.domain.market_rules import (
    EvaluatedTrade,
    MarketRuleProfile,
    SubmittedTrade,
)


class TradingCalendarOpenDateResolver:
    def __init__(self, calendar: TradingCalendarVersion):
        self._calendar = calendar

    def next_date(self, current: date) -> date:
        return current + timedelta(days=1)

    def next_open_date(self, current: date) -> date:
        candidates = [
            day.date for day in self._calendar.days if day.date > current and day.kind in {"full", "half"}
        ]
        if not candidates:
            raise MarketRuleCalendarUnavailableError(current)
        return min(candidates)

    def trading_date_for(self, value: date) -> date:
        try:
            return self.next_open_date(value - timedelta(days=1))
        except MarketRuleCalendarUnavailableError as exc:
            raise MarketRuleCalendarUnavailableError(value) from exc


class MarketRuleCalendarUnavailableError(Exception):
    def __init__(self, value: date):
        """Calendar cannot satisfy a later open date."""
        super().__init__(f"trading calendar has no later open date than {value.isoformat()}")


def _empty(
    *,
    valid_quantity: Decimal | None = None,
    valid_price: Decimal | None = None,
    rejection_reason: str,
    rule_source_version_id: str | None,
    matches: Iterable[str] = (),
) -> EvaluatedTrade:
    return EvaluatedTrade(
        filled_quantity=Decimal("0"),
        valid_quantity=valid_quantity,
        valid_price=valid_price,
        sell_available_date=None,
        security_settlement_date=None,
        cash_settlement_date=None,
        rejection_reason=rejection_reason,
        rule_source_version_id=rule_source_version_id,
        matches=tuple(matches),
    )


class PureMarketRuleEvaluator:
    def evaluate_trade(
        self,
        submitted: SubmittedTrade,
        profile: MarketRuleProfile | None,
        calendar: TradingCalendarVersion | None = None,
        matches: Iterable[str] = (),
        next_permitted_date: date | None = None,
    ) -> EvaluatedTrade:
        requested_quantity = Decimal(str(submitted.requested_quantity))
        requested_price = Decimal(str(submitted.requested_price))
        sellable_quantity = Decimal(str(submitted.sellable_quantity))
        match_ids = tuple(matches)
        if profile is None:
            reason = "missing-market-rule-profile" if not match_ids else "ambiguous-market-rule-profile"
            return _empty(rejection_reason=reason, rule_source_version_id=None, matches=match_ids)
        valid_quantity = _floor_to_quantity(requested_quantity, profile.trading_lot)
        valid_price = _floor_to_tick(requested_price, profile.tick_size)
        if requested_price <= 0:
            return _empty(
                valid_quantity=valid_quantity,
                valid_price=Decimal("0"),
                rejection_reason="invalid-price",
                rule_source_version_id=profile.version_id,
                matches=match_ids,
            )
        if submitted.session_kind not in profile.permitted_session_types:
            deferred = next_permitted_date or (
                PureMarketRuleEvaluator.next_permitted_date(
                    profile=profile, calendar=calendar, trade_date=submitted.trade_date
                )
                if calendar is not None
                else None
            )
            if deferred is None or deferred > submitted.trade_date:
                return _empty(
                    valid_quantity=valid_quantity,
                    valid_price=valid_price,
                    rejection_reason=(
                        "deferred:" + deferred.isoformat()
                        if deferred is not None and deferred > submitted.trade_date
                        else "session-not-permitted"
                    ),
                    rule_source_version_id=profile.version_id,
                    matches=match_ids,
                )
            if next_permitted_date is not None and next_permitted_date > submitted.trade_date:
                return _empty(
                    valid_quantity=valid_quantity,
                    valid_price=valid_price,
                    rejection_reason=f"deferred:{next_permitted_date.isoformat()}",
                    rule_source_version_id=profile.version_id,
                    matches=match_ids,
                )
        if abs(valid_quantity) == 0:
            return _empty(
                valid_quantity=valid_quantity,
                valid_price=valid_price,
                rejection_reason="invalid-lot",
                rule_source_version_id=profile.version_id,
                matches=match_ids,
            )
        if submitted.side == "SELL" and abs(valid_quantity) > sellable_quantity:
            return _empty(
                valid_quantity=valid_quantity,
                valid_price=valid_price,
                rejection_reason="sell-quantity-unavailable",
                rule_source_version_id=profile.version_id,
                matches=match_ids,
            )
        blocked, block_reason = _blocked_for_trade(submitted, requested_price)
        if blocked:
            assert block_reason is not None
            return _empty(
                valid_quantity=valid_quantity,
                valid_price=valid_price,
                rejection_reason=block_reason,
                rule_source_version_id=profile.version_id,
                matches=match_ids,
            )
        if calendar is None:
            raise MarketRuleCalendarUnavailableError(submitted.trade_date)
        resolver = TradingCalendarOpenDateResolver(calendar)
        return EvaluatedTrade(
            filled_quantity=valid_quantity,
            valid_quantity=valid_quantity,
            valid_price=valid_price,
            sell_available_date=_sell_available_date(submitted, profile, resolver),
            security_settlement_date=self._advance_open_dates(
                submitted.trade_date, profile.security_settlement_open_dates, resolver
            ),
            cash_settlement_date=self._advance_open_dates(
                submitted.trade_date, profile.cash_settlement_open_dates, resolver
            ),
            rejection_reason=block_reason,
            rule_source_version_id=profile.version_id,
            matches=match_ids,
        )

    def evaluate_batch(
        self,
        batch: Iterable[
            tuple[
                SubmittedTrade, MarketRuleProfile | None, TradingCalendarVersion, Iterable[str], date | None
            ]
        ],
    ) -> Iterator[EvaluatedTrade]:
        for submitted, profile, calendar, matches, next_permitted_date in batch:
            yield self.evaluate_trade(
                submitted=submitted,
                profile=profile,
                calendar=calendar,
                matches=matches,
                next_permitted_date=next_permitted_date,
            )

    @staticmethod
    def _advance_open_dates(
        trade_date: date, offset_days: int, date_provider: TradingCalendarOpenDateResolver
    ) -> date | None:
        for _ in range(offset_days):
            trade_date = date_provider.next_open_date(trade_date)
        return trade_date

    @staticmethod
    def next_permitted_date(
        profile: MarketRuleProfile,
        calendar: TradingCalendarVersion,
        trade_date: date,
    ) -> date | None:
        for day in calendar.days:
            if day.date < trade_date or day.kind not in {"full", "half"}:
                continue
            for session in day.sessions:
                if session.kind in profile.permitted_session_types:
                    return day.date
        return None


def _floor_to_quantity(requested_quantity: Decimal, lot_size: int) -> Decimal:
    units = abs(requested_quantity) // Decimal(lot_size) * Decimal(lot_size)
    return units if requested_quantity > 0 else -units


def _floor_to_tick(requested_price: Decimal, tick_size: Decimal) -> Decimal:
    return requested_price // tick_size * tick_size


def _blocked_for_trade(submitted: SubmittedTrade, requested_price: Decimal) -> tuple[bool, str | None]:
    if submitted.halt_status != "ACTIVE":
        return True, f"halt:{submitted.halt_status}"
    reference = submitted.reference_price
    if reference is None or reference <= 0:
        return True, "price-limit-source-missing"
    if submitted.market == "A_SHARE":
        percentage = submitted.market_data_price_limit_percent
        if percentage is None:
            return True, "price-limit-source-missing"
        if abs((requested_price - reference) / reference) > percentage:
            return True, "price-limit"
        return False, None
    band = submitted.market_data_price_band_percent
    if band is None:
        return True, "provider-band-missing"
    if abs((requested_price - reference) / reference) > band:
        return True, "provider-price-band"
    return False, None


def _sell_available_date(
    submitted: SubmittedTrade,
    profile: MarketRuleProfile,
    resolver: TradingCalendarOpenDateResolver,
) -> date:
    if profile.sell_availability_rule == "SAME_MARKET_DATE":
        return submitted.trade_date
    return resolver.next_open_date(submitted.trade_date)
