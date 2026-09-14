from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from urllib.parse import quote

from mmqp.adapters.data_connectors.base import DailyBarConnector, NormalizedDailyBar
from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.normalize import (
    _currency,
    _decimal_at,
    _exact_item,
    _invalid_response,
    _number_at,
    _object,
    _provenance_id,
)
from mmqp.adapters.data_connectors.provider_response import envelope


@dataclass(frozen=True, slots=True, kw_only=True)
class YahooFinanceDailyBarConnector(DailyBarConnector):
    transport: HTTPTransport

    @property
    def provider(self) -> str:
        return "yfinance"

    def fetch(self, provider_code: str, trading_date: date) -> NormalizedDailyBar:
        encoded_code = quote(provider_code, safe="")
        start = int(datetime(trading_date.year, trading_date.month, trading_date.day, tzinfo=UTC).timestamp())
        end = start + 86_400
        endpoint = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{encoded_code}?period1={start}&period2={end}&interval=1d&includePrePost=false"
        )
        payload = self.transport.json(endpoint)
        chart = _object(payload.get("chart"))
        result = _exact_item(chart.get("result"))
        quote_items = _object(result.get("indicators")).get("quote")
        quote_values = _exact_item(quote_items)
        timestamps = result.get("timestamp")
        if not isinstance(timestamps, list):
            raise _invalid_response("timestamp")
        date_key = trading_date.isoformat()
        matches = [index for index, timestamp in enumerate(timestamps) if timestamp == date_key]
        if len(matches) != 1:
            raise _invalid_response("date")
        index = matches[0]
        meta = _object(result.get("meta"))
        return NormalizedDailyBar(
            trading_date=trading_date,
            open=_decimal_at(quote_values, "open", index),
            high=_decimal_at(quote_values, "high", index),
            low=_decimal_at(quote_values, "low", index),
            close=_decimal_at(quote_values, "close", index),
            volume=_number_at(quote_values, "volume", index),
            turnover=Decimal("0"),
            trading_currency=_currency(str(meta.get("currency", "")).upper()),
            provider_available_at=datetime.combine(trading_date, time(22, 0), tzinfo=UTC),
            retrieved_at=datetime.now(UTC),
            provider=self.provider,
            provider_code=provider_code,
            provenance_id=_provenance_id("yfinance", encoded_code, trading_date),
            response=envelope(
                self.provider,
                encoded_code,
                "https://query1.finance.yahoo.com",
                source_version=str(meta.get("fullExchangeName") or "chart-v8"),
            ),
        )
