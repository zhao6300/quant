from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from mmqp.adapters.data_connectors.base import DailyBarConnector, NormalizedDailyBar
from mmqp.adapters.data_connectors.normalize import _invalid_response, _provenance_id
from mmqp.adapters.data_connectors.provider_response import envelope
from mmqp.domain.calendars import TradingCalendarDay, TradingCalendarVersion, TradingSession


class _ModuleDailyBarConnector(DailyBarConnector):
    _module: Any

    def __init__(self, module: Any) -> None:
        self._module = module

    @property
    def provider(self) -> str:
        raise NotImplementedError

    def fetch(self, provider_code: str, trading_date: date) -> NormalizedDailyBar:
        record = self._row_record(provider_code, trading_date)
        return _daily_bar(self.provider, provider_code, record, trading_date)

    def _row_record(self, provider_code: str, trading_date: date) -> dict[str, Any]:
        raise NotImplementedError


class AkShareDailyBarConnector(_ModuleDailyBarConnector):
    @property
    def provider(self) -> str:
        return "akshare"

    def _row_record(self, provider_code: str, trading_date: date) -> dict[str, Any]:
        frame = self._module.__getattribute__("stock_zh_a_hist")(
            symbol=provider_code,
            period="daily",
            start_date=trading_date.isoformat(),
            end_date=trading_date.isoformat(),
            adjust="qfq",
        )
        records = frame.to_dict(orient="records")
        for source_record in records:
            if not isinstance(source_record, dict):
                continue
            if source_record.get("日期") == trading_date.isoformat():
                record: dict[str, Any] = source_record
                return record
        raise _invalid_response("missing-date")


class BaoStockDailyBarConnector(_ModuleDailyBarConnector):
    @property
    def provider(self) -> str:
        return "baostock"

    def _row_record(self, provider_code: str, trading_date: date) -> dict[str, Any]:
        self._module.__getattribute__("login")()
        try:
            result = self._module.__getattribute__("query_history_k_data_plus")(
                provider_code,
                "date,code,open,high,low,close,volume,amount",
                start_date=trading_date.isoformat(),
                end_date=trading_date.isoformat(),
                frequency="d",
            )
        finally:
            self._module.__getattribute__("logout")()
        for row in result.data:
            repaired_record = dict(zip(result.fields, row, strict=True))
            if repaired_record.get("date") == trading_date.isoformat():
                returned_record: dict[str, Any] = repaired_record
                return returned_record
        raise _invalid_response("missing-date")


def _daily_bar(
    provider: str,
    provider_code: str,
    row: Mapping[str, Any],
    trading_date: date,
) -> NormalizedDailyBar:
    return NormalizedDailyBar(
        trading_date=trading_date,
        open=Decimal(str(row["open"])),
        high=Decimal(str(row["high"])),
        low=Decimal(str(row["low"])),
        close=Decimal(str(row["close"])),
        volume=Decimal(str(row["volume"])),
        turnover=Decimal(str(row["amount"])),
        trading_currency="CNY",
        provider_available_at=datetime.combine(trading_date, time(22, 0), tzinfo=UTC),
        retrieved_at=datetime.now(UTC),
        provider=provider,
        provider_code=provider_code,
        provenance_id=_provenance_id(provider, provider_code, trading_date),
        response=envelope(provider, provider_code, "package", source_version="package-1"),
    )


@dataclass(frozen=True, slots=True)
class ExchangeCalendarSource:
    _module: Any

    module: Any

    @property
    def provider(self) -> str:
        return "exchange_calendars"

    def fetch(self, provider_code: str, start: date, end: date) -> TradingCalendarVersion:
        calendar = self._module.__getattribute__("get_calendar")(provider_code)
        schedule = calendar.schedule(start.isoformat(), end.isoformat())
        days = tuple(
            TradingCalendarDay(
                market=provider_code,
                exchange=provider_code,
                date=calendar_day(value),
                kind="full",
                sessions=(TradingSession(start="00:00", end="23:59", kind="regular"),),
            )
            for value in schedule.index
        )
        return TradingCalendarVersion(
            version_id=_calendar_version_id(self.provider, provider_code, start, end),
            market=provider_code,
            exchange=provider_code,
            timezone="UTC",
            effective_from=start,
            effective_to=end,
            days=days,
        )


@dataclass(frozen=True, slots=True)
class PandasMarketCalendarsSource:
    _module: Any
    module: Any

    @property
    def provider(self) -> str:
        return "pandas_market_calendars"

    def fetch(self, provider_code: str, start: date, end: date) -> TradingCalendarVersion:
        calendar = self._module.__getattribute__("get_calendar")(provider_code)
        schedule = calendar.schedule(start_date=start.isoformat(), end_date=end.isoformat())
        days = tuple(
            TradingCalendarDay(
                market=provider_code,
                exchange=provider_code,
                date=calendar_day(value),
                kind="full",
                sessions=(TradingSession(start="00:00", end="23:59", kind="regular"),),
            )
            for value in schedule.index
        )
        return TradingCalendarVersion(
            version_id=_calendar_version_id(self.provider, provider_code, start, end),
            market=provider_code,
            exchange=provider_code,
            timezone="UTC",
            effective_from=start,
            effective_to=end,
            days=days,
        )


def calendar_day(value: object) -> date:
    if isinstance(value, date):
        return value
    timestamp = getattr(value, "date", None)
    if callable(timestamp):
        candidate = timestamp()
        if isinstance(candidate, date):
            return candidate
    raise _invalid_response("calendar-date")


def _calendar_version_id(provider: str, calendar_code: str, start: date, end: date) -> str:
    payload = json.dumps(
        {"calendar": calendar_code, "end": end.isoformat(), "provider": provider, "start": start.isoformat()},
        sort_keys=True,
    )
    return f"calendar-{provider}-v1-{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"
