from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
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
        result, timestamps = self._chart_result(self._recent_chart(provider_code, trading_date))
        matches = self._matching_indexes(timestamps, trading_date)
        if len(matches) == 1:
            return self._normalized(provider_code, encoded_code, result, trading_date, matches[0])
        fallback_date = self._fallback_date(timestamps, trading_date)
        if fallback_date is None:
            raise _invalid_response("missing-date")
        prior_matches = self._matching_indexes(timestamps, fallback_date)
        if len(prior_matches) != 1:
            raise _invalid_response("missing-date")
        return self._normalized(provider_code, encoded_code, result, fallback_date, prior_matches[0])

    def _recent_chart(self, provider_code: str, trading_date: date) -> dict[str, object]:
        endpoint = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{quote(provider_code, safe='')}"
            f"?period1={self._day_start(trading_date - timedelta(days=10))}"
            f"&period2={self._day_end(trading_date) + 1}"
            "&interval=1d&includePrePost=false"
        )
        payload = self.transport.json(endpoint)
        return _object(payload.get("chart"))

    @staticmethod
    def _chart_result(chart: dict[str, object]) -> tuple[dict[str, Any], list[Any]]:
        result = _exact_item(chart.get("result"))
        timestamps = result.get("timestamp")
        if not isinstance(timestamps, list):
            raise _invalid_response("timestamp")
        return result, timestamps

    @staticmethod
    def _matching_indexes(timestamps: list[Any], trading_date: date) -> list[int]:
        return [
            index
            for index, timestamp in enumerate(timestamps)
            if yahoo_observation_date(timestamp) == trading_date
        ]

    @staticmethod
    def _fallback_date(timestamps: list[Any], trading_date: date) -> date | None:
        preceding: list[tuple[int, date]] = []
        for index, timestamp in enumerate(timestamps):
            observed = yahoo_observation_date(timestamp)
            if observed is not None and observed < trading_date:
                preceding.append((index, observed))
        if not preceding:
            return None
        return max(preceding, key=lambda item: item[0])[1]

    @staticmethod
    def _day_start(trading_date: date) -> int:
        return int(datetime.combine(trading_date, time(0, 0), tzinfo=UTC).timestamp())

    @staticmethod
    def _day_end(trading_date: date) -> int:
        return int(datetime.combine(trading_date, time(23, 59), tzinfo=UTC).timestamp())

    @staticmethod
    def _normalized(
        provider_code: str,
        encoded_code: str,
        result: dict[str, Any],
        trading_date: date,
        index: int,
    ) -> NormalizedDailyBar:
        quote_items = _object(result.get("indicators")).get("quote")
        quote_values = _exact_item(quote_items)
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
            as_of=datetime.now(UTC),
            provider="yfinance",
            provider_code=provider_code,
            provenance_id=_provenance_id("yfinance", encoded_code, trading_date),
            response=envelope(
                "yfinance",
                encoded_code,
                "https://query1.finance.yahoo.com",
                source_version=str(meta.get("fullExchangeName") or "chart-v8"),
            ),
        )


def yahoo_observation_date(timestamp: Any) -> date | None:
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, UTC).date()
    if isinstance(timestamp, str):
        try:
            return date.fromisoformat(timestamp)
        except ValueError:
            return None
    return None
