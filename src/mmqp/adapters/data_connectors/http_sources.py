from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import quote

from mmqp.adapters.data_connectors.base import DailyBarConnector, NormalizedDailyBar
from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.normalize import (
    _decimal,
    _invalid_response,
    _object,
    _provenance_id,
)
from mmqp.adapters.data_connectors.provider_response import envelope


class PostJSONTransport(Protocol):
    def post_json(self, url: str, form: Mapping[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class TusharePOSTTransport:
    timeout: float = 30.0

    def post_json(self, url: str, form: Mapping[str, Any]) -> dict[str, Any]:
        payload = urllib.parse.urlencode(dict(form)).encode("utf-8")
        request = urllib.request.Request(url, data=payload)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise _invalid_response("tushare") from error
        if not isinstance(parsed, dict):
            raise _invalid_response("tushare")
        return parsed


@dataclass(frozen=True, slots=True, kw_only=True)
class TushareDailyBarConnector(DailyBarConnector):
    transport: PostJSONTransport
    api_token: str

    @property
    def provider(self) -> str:
        return "tushare"

    def fetch(self, provider_code: str, trading_date: date) -> NormalizedDailyBar:
        response = self.transport.post_json(
            "https://api.tushare.pro",
            {
                "api_name": "daily",
                "token": self.api_token,
                "params": {"trade_date": trading_date.isoformat()},
            },
        )
        body = _object(response.get("data"))
        rows = body.get("items")
        fields = body.get("fields")
        if not isinstance(rows, list) or not rows or not isinstance(fields, list):
            raise _invalid_response("tushare")
        names = [str(value) for value in fields]
        row_map = dict(zip(names, rows[0], strict=True))
        return _daily_bar(
            provider_code=provider_code,
            trading_date=trading_date,
            row=row_map,
            trading_currency="CNY",
            provider="tushare",
            origin="https://api.tushare.pro",
            source_version="pro-v1",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RestDailyBarSpec:
    source_id: str
    provider: str
    trading_currency: str
    origin: str
    source_version: str
    api_query_field: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class RestDailyBarConnector(DailyBarConnector):
    source: RestDailyBarSpec
    transport: HTTPTransport

    @property
    def provider(self) -> str:
        return self.source.provider

    def fetch(self, provider_code: str, trading_date: date) -> NormalizedDailyBar:
        row = self._row(provider_code, trading_date)
        values = self._values(row)
        return _normalized(
            provider_code,
            trading_date,
            values,
            self.source.trading_currency,
            self.source.provider,
            self.source.origin,
            self.source.source_version,
        )

    def _row(self, provider_code: str, trading_date: date) -> dict[str, Any]:
        payload = self.transport.json(self._endpoint(provider_code, trading_date))
        source_id = self.source.source_id
        day = trading_date.isoformat()
        if source_id == "alpha-vantage":
            row = _object(_object(payload.get("Time Series (Daily)")).get(day))
        elif source_id == "financial-modeling-prep":
            row = _matching_row(_array(payload.get("historical")), "date", day)
        elif source_id == "finnhub":
            row = _finnhub_row(payload, trading_date)
        elif source_id == "tiingo":
            row = _matching_row(_array(payload), "date", day)
        elif source_id == "polygon-io":
            row = _matching_row(_array(payload.get("results")), "t", trading_date, timestamp=True)
        elif source_id == "iex-cloud":
            row = _matching_row(_array(payload), "date", day.replace("-", ""), exact=False)
        elif source_id == "twelve-data":
            row = _matching_row(_array(payload.get("values")), "datetime", day)
        elif source_id == "nasdaq-data-link":
            table = _object(payload.get("datatable"))
            records = _array(table.get("data"))
            if not records:
                raise _invalid_response("missing-date")
            record = _array(records[0])
            row = {str(index): value for index, value in enumerate(record)}
        elif source_id == "ecb":
            row = {"0": _object(payload.get("rates")).get(day)}
        else:
            raise _invalid_response("unsupported-source")
        if not row:
            raise _invalid_response("missing-date")
        return row

    def _endpoint(self, provider_code: str, trading_date: date) -> str:
        encoded = quote(provider_code, safe="")
        day = trading_date.isoformat()
        secret = self.source.api_query_field
        source_id = self.source.source_id
        if source_id == "alpha-vantage":
            return (
                "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
                f"&symbol={encoded}&date={day}&apikey={secret}"
            )
        if source_id == "financial-modeling-prep":
            return (
                "https://financialmodelingprep.com/api/v3/historical-price-full/"
                f"{encoded}?from={day}&to={day}&apikey={secret}"
            )
        if source_id == "finnhub":
            return (
                "https://finnhub.io/api/v1/stock/candle"
                f"?symbol={encoded}&from={day}&to={day}&resolution=D&token={secret}"
            )
        if source_id == "tiingo":
            return f"https://api.tiingo.com/tiingo/daily/{encoded}/prices?startDate={day}&endDate={day}&token={secret}"
        if source_id == "polygon-io":
            return f"https://api.polygon.io/v2/aggs/ticker/{encoded}/range/1/day/{day}/{day}?apiKey={secret}"
        if source_id == "iex-cloud":
            return f"https://cloud.iexapis.com/v1/stock/{encoded}/chart/date/{day}?range=1d&token={secret}"
        if source_id == "twelve-data":
            return f"https://api.twelvedata.com/time_series?symbol={encoded}&interval=1day&date={day}&apikey={secret}"
        if source_id == "nasdaq-data-link":
            return (
                "https://data.nasdaq.com/api/v3/datatables/QUOTEMEDIA/PRICES"
                f"?ticker.ticker={encoded}&date={day}&api_key={secret}"
            )
        if source_id == "ecb":
            return f"https://data-api.ecb.europa.eu/service/data/EXR/D/{encoded}.EUR.SP00.A?format=jsondata"
        raise _invalid_response("unsupported-source")

    def _values(self, row: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
        source_id = self.source.source_id
        if source_id == "alpha-vantage":
            return (
                _decimal(row["1. open"]),
                _decimal(row["2. high"]),
                _decimal(row["3. low"]),
                _decimal(row["4. close"]),
                _number(row["5. volume"]),
            )
        if source_id == "nasdaq-data-link":
            ordered = [row[str(index)] for index in range(5)]
            if len(ordered) != 5:
                raise _invalid_response("nasdaq")
        decimal_values = tuple(_decimal(value) for value in ordered)
        return decimal_values[0], decimal_values[1], decimal_values[2], decimal_values[3], decimal_values[4]
        if source_id == "ecb":
            rate = _decimal(row["0"])
            return rate, rate, rate, rate, Decimal("0")
        return (
            _decimal(_maybe_value(row, "open", "adjOpen")),
            _decimal(_maybe_value(row, "high", "adjHigh")),
            _decimal(_maybe_value(row, "low", "adjLow")),
            _decimal(_maybe_value(row, "close", "adjClose")),
            _number(_maybe_value(row, "volume", "adjVolume", "v")),
        )


def _maybe_value(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return None


def _number(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as error:  # pragma: no cover - shared invalid-value path
        raise _invalid_response("number") from error
    if result.is_finite():
        return result
    raise _invalid_response("number")


def _daily_bar(
    *,
    provider_code: str,
    trading_date: date,
    row: Mapping[str, Any],
    trading_currency: str,
    provider: str,
    origin: str,
    source_version: str,
) -> NormalizedDailyBar:
    return _normalized(
        provider_code,
        trading_date,
        (
            _decimal(row["open"]),
            _decimal(row["high"]),
            _decimal(row["low"]),
            _decimal(row["close"]),
            _number(row["volume"]),
        ),
        trading_currency,
        provider,
        origin,
        source_version,
    )


def _normalized(
    provider_code: str,
    trading_date: date,
    values: tuple[Decimal, Decimal, Decimal, Decimal, Decimal],
    trading_currency: str,
    provider: str,
    origin: str,
    source_version: str,
) -> NormalizedDailyBar:
    encoded_code = quote(provider_code, safe="")
    return NormalizedDailyBar(
        trading_date=trading_date,
        open=values[0],
        high=values[1],
        low=values[2],
        close=values[3],
        volume=values[4],
        turnover=Decimal("0"),
        trading_currency=trading_currency,
        provider_available_at=datetime.combine(trading_date, time(22, 0), tzinfo=UTC),
        retrieved_at=datetime.now(UTC),
        as_of=datetime.now(UTC),
        provider=provider,
        provider_code=provider_code,
        provenance_id=_provenance_id(provider, encoded_code, trading_date),
        response=envelope(provider, encoded_code, origin, source_version=source_version),
    )


def _array(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _matching_row(
    rows: list[Any],
    key: str,
    expected: object,
    *,
    exact: bool = True,
    timestamp: bool = False,
) -> dict[str, Any]:
    for candidate in rows:
        if not isinstance(candidate, Mapping):
            continue
        value = candidate.get(key)
        if (
            timestamp
            and isinstance(value, int | float)
            and datetime.fromtimestamp(value, UTC).date() == expected
        ):
            return dict(candidate)
        text = str(value)
        if (exact and text == expected) or (not exact and text == str(expected)):
            return dict(candidate)
    raise _invalid_response("missing-date")


def _finnhub_row(payload: dict[str, Any], trading_date: date) -> dict[str, Any]:
    timestamps = _array(payload.get("t"))
    names = ("o", "high", "low", "c", "v")
    values = tuple(_array(payload.get(name)) for name in names)
    for index, timestamp in enumerate(timestamps):
        if datetime.fromtimestamp(timestamp, UTC).date() == trading_date:
            return dict(zip(names, (item[index] for item in values), strict=True))
    raise _invalid_response("missing-date")


def rest_daily_bar_connectors(transport: HTTPTransport) -> dict[str, RestDailyBarConnector]:
    source = _rest_daily_bar_source
    return {
        source(a).source_id: RestDailyBarConnector(source=source(a), transport=transport)
        for a in (
            (
                "alpha-vantage",
                "alphavantage",
                "USD",
                "https://www.alphavantage.co",
                "timeseries-v1",
                "apikey",
            ),
            (
                "financial-modeling-prep",
                "financialmodelingprep",
                "USD",
                "https://financialmodelingprep.com",
                "v3",
                "apikey",
            ),
            ("finnhub", "finnhub", "USD", "https://finnhub.io", "v1", "token"),
            ("tiingo", "tiingo", "USD", "https://api.tiingo.com", "v1", "token"),
            ("polygon-io", "polygon", "USD", "https://api.polygon.io", "v2", "apiKey"),
            ("iex-cloud", "iexcloud", "USD", "https://cloud.iexapis.com", "v1", "token"),
            ("twelve-data", "twelvedata", "USD", "https://api.twelvedata.com", "v1", "apikey"),
            ("nasdaq-data-link", "nasdaq-data-link", "USD", "https://data.nasdaq.com", "v3", "api_key"),
            ("ecb", "ecb", "EUR", "https://data-api.ecb.europa.eu", "sdmx-v3", ""),
        )
    }


def _rest_daily_bar_source(
    arguments: tuple[str, str, str, str, str, str],
) -> RestDailyBarSpec:
    source_id, provider, currency, origin, source_version, auth_field = arguments
    return RestDailyBarSpec(
        source_id=source_id,
        provider=provider,
        trading_currency=currency,
        origin=origin,
        source_version=source_version,
        api_query_field=auth_field,
    )
