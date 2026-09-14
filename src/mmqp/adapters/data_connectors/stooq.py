from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from urllib.parse import quote

from mmqp.adapters.data_connectors.base import DailyBarConnector, NormalizedDailyBar
from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.normalize import (
    _decimal_field,
    _invalid_response,
    _number_field,
    _provenance_id,
    _stooq_currency,
)
from mmqp.adapters.data_connectors.provider_response import envelope


@dataclass(frozen=True, slots=True, kw_only=True)
class StooqDailyBarConnector(DailyBarConnector):
    transport: HTTPTransport

    @property
    def provider(self) -> str:
        return "stooq"

    def fetch(self, provider_code: str, trading_date: date) -> NormalizedDailyBar:
        encoded_code = quote(provider_code, safe="")
        endpoint = (
            "https://stooq.com/q/d/l/"
            f"?s={encoded_code}"
            f"&d1={trading_date.isoformat()}"
            f"&d2={trading_date.isoformat()}&i=d"
        )
        payload = self.transport.text(endpoint)
        rows = list(csv.DictReader(io.StringIO(payload), strict=True))
        selected = [row for row in rows if row.get("Date") == trading_date.isoformat()]
        if not selected:
            raise _invalid_response("missing-date")
        values = selected[0]
        return NormalizedDailyBar(
            trading_date=trading_date,
            open=_decimal_field(values, "Open"),
            high=_decimal_field(values, "High"),
            low=_decimal_field(values, "Low"),
            close=_decimal_field(values, "Close"),
            volume=_number_field(values, "Volume"),
            turnover=Decimal("0"),
            trading_currency=_stooq_currency(provider_code),
            provider_available_at=datetime.combine(trading_date, time(22, 0), tzinfo=UTC),
            retrieved_at=datetime.now(UTC),
            provider=self.provider,
            provider_code=provider_code,
            provenance_id=_provenance_id("stooq", encoded_code, trading_date),
            response=envelope(self.provider, encoded_code, "https://stooq.com", source_version="csv-1"),
        )
