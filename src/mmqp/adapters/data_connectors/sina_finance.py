from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from mmqp.adapters.data_connectors.base import DailyBarConnector, NormalizedDailyBar
from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.normalize import (
    _decimal,
    _invalid_response,
    _provenance_id,
)
from mmqp.adapters.data_connectors.provider_response import envelope


@dataclass(frozen=True, slots=True, kw_only=True)
class SinaFinanceDailyBarConnector(DailyBarConnector):
    transport: HTTPTransport

    @property
    def provider(self) -> str:
        return "sina-finance"

    def fetch(self, provider_code: str, trading_date: date) -> NormalizedDailyBar:
        symbol = _sina_symbol(provider_code)
        endpoint = (
            "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            "CN_MarketData.getKLineData"
            f"?symbol={quote(symbol, safe='')}"
            "&scale=240&ma=no&datalen=500"
        )
        rows = self._rows(endpoint, trading_date)
        selected = next((row for row in rows if row.get("day") == trading_date.isoformat()), None)
        if selected is None:
            raise _invalid_response("missing-date")
        return _normalized(provider_code, trading_date, selected)

    def _rows(self, endpoint: str, _: date) -> list[dict[str, Any]]:
        payload = self.transport.text(endpoint)
        try:
            values = json.loads(payload)
        except (json.JSONDecodeError, UnicodeError) as error:
            raise _invalid_response("json") from error
        if not isinstance(values, list):
            raise _invalid_response("json")
        return [value for value in values if isinstance(value, dict)]


def _sina_symbol(provider_code: str) -> str:
    local_code = provider_code.replace(".SS", "").replace(".SZ", "")
    if len(local_code) != 6 or not local_code.isdigit():
        raise _invalid_response("symbol")
    prefix = "sh" if local_code.startswith("6") else "sz"
    return f"{prefix}{local_code}"


def _normalized(provider_code: str, trading_date: date, row: dict[str, Any]) -> NormalizedDailyBar:
    volume = _decimal(row.get("volume"))
    return NormalizedDailyBar(
        trading_date=trading_date,
        open=_decimal(row.get("open")),
        high=_decimal(row.get("high")),
        low=_decimal(row.get("low")),
        close=_decimal(row.get("close")),
        volume=volume,
        turnover=Decimal("0"),
        trading_currency="CNY",
        provider_available_at=datetime.combine(trading_date, time(22, 0), tzinfo=UTC),
        retrieved_at=datetime.now(UTC),
        as_of=datetime.now(UTC),
        provider="sina-finance",
        provider_code=provider_code,
        provenance_id=_provenance_id("sina-finance", provider_code, trading_date),
        response=envelope(
            "sina-finance",
            provider_code,
            "https://money.finance.sina.com.cn",
            source_version="daily-1",
        ),
    )
