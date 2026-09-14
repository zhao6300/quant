from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any
from urllib.parse import quote

from mmqp.adapters.data_connectors.base import FundamentalFactConnector, NormalizedFundamentalFact
from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.normalize import (
    _currency,
    _decimal_value,
    _invalid_response,
    _provenance_id,
)
from mmqp.adapters.data_connectors.provider_response import fact_envelope


@dataclass(frozen=True, slots=True, kw_only=True)
class SECEDGARConnector(FundamentalFactConnector):
    transport: HTTPTransport

    @property
    def provider(self) -> str:
        return "sec-edgar"

    def fetch(self, provider_code: str, metric_code: str) -> NormalizedFundamentalFact:
        entity_url = (
            "https://data.sec.gov/api/xbrl/companyconcept/"
            f"CIK{provider_code}/us-gaap/{quote(metric_code, safe='')}.json"
        )
        payload = self.transport.json(entity_url)
        raw_cik = payload.get("cik")
        if not isinstance(raw_cik, int):
            raise _invalid_response("cik")
        canonical_asset_id = f"SEC-EDGAR:{raw_cik}"
        _name(payload.get("entityName"))
        selected_unit = "USD"
        unit_series = _series(payload.get("units"), selected_unit)
        event = unit_series[0]
        period_start = date.fromisoformat(str(event.get("start", "")))
        period_end = date.fromisoformat(str(event.get("end", "")))
        currency = _currency(str(payload.get("currencyCode", "USD")).upper())
        value = _decimal_value(event.get("val"))
        return NormalizedFundamentalFact(
            canonical_asset_id=canonical_asset_id,
            metric_name=f"us-gaap:{metric_code}",
            value=value,
            unit=selected_unit,
            currency=currency,
            period_start=period_start,
            period_end=period_end,
            provider_available_at=datetime.combine(period_end, time(23, 0), tzinfo=UTC),
            provider=self.provider,
            provenance_id=_provenance_id(self.provider, canonical_asset_id, period_end),
            response=fact_envelope(self.provider, canonical_asset_id, metric_code, entity_url),
        )


def _name(value: object) -> str:
    if not isinstance(value, str):
        return "SEC"
    return value if value else "SEC"


def _series(raw: object, unit: str) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        raise _invalid_response("units")
    selected = raw.get(unit)
    if not isinstance(selected, list) or not selected:
        raise _invalid_response("unit-series")
    if not all(isinstance(item, dict) for item in selected):
        raise _invalid_response("unit-event")
    return selected
