from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from mmqp.adapters.data_connectors.base import FundamentalFactConnector, NormalizedFundamentalFact
from mmqp.adapters.data_connectors.http import HTTPTransport
from mmqp.adapters.data_connectors.normalize import _decimal, _invalid_response, _object, _provenance_id
from mmqp.adapters.data_connectors.provider_response import fact_envelope


@dataclass(frozen=True, slots=True)
class NormalizedCorporateActionRecord:
    provider_code: str
    posting_date: date
    announcement_id: str
    event_type: str
    retrieved_at: datetime
    provider: str
    provenance_id: str
    response: dict[str, Any]


@dataclass(frozen=True, slots=True)
class HKEXNewsCorporateActionConnector:
    transport: HTTPTransport

    @property
    def provider(self) -> str:
        return "hkex"

    def fetch(self, provider_code: str, posting_date: date) -> NormalizedCorporateActionRecord:
        payload = self.transport.json(
            "https://www.hkexnews.hk/api/titlesearch/titlesearch.json"
            f"?lang=zh&market=SEHK&stockCode={provider_code}&from={posting_date.isoformat()}"
            f"&to={posting_date.isoformat()}&documentType=-1&title="
        )
        results = payload.get("result")
        if not isinstance(results, list) or not results:
            raise _invalid_response("missing-event")
        selected = next(
            (item for item in results if isinstance(item, Mapping) and isinstance(item.get("id"), str)), None
        )
        if selected is None:
            raise _invalid_response("event")
        selected = dict(selected)
        identifier = str(selected["id"])
        return NormalizedCorporateActionRecord(
            provider_code=provider_code,
            posting_date=posting_date,
            announcement_id=identifier,
            event_type=str(selected.get("title", "announcement")),
            retrieved_at=datetime.now(UTC),
            provider=self.provider,
            provenance_id=_provenance_id(self.provider, provider_code, identifier),
            response=dict(payload),
        )


@dataclass(frozen=True, slots=True)
class FREDObservationsConnector(FundamentalFactConnector):
    transport: HTTPTransport
    api_key: str

    @property
    def provider(self) -> str:
        return "fred"

    def fetch(self, provider_code: str, metric_code: str) -> NormalizedFundamentalFact:
        endpoint = (
            "https://api.stlouisfed.org/fred/series/observations?series_id="
            f"{metric_code}&api_key={self.api_key}&file_type=json&sort_order=asc"
        )
        payload = self.transport.json(endpoint)
        observations = payload.get("observations")
        if not isinstance(observations, list) or not observations:
            raise _invalid_response("missing-series")
        selected = _object(observations[-1])
        period = date.fromisoformat(str(selected.get("date")))
        return NormalizedFundamentalFact(
            canonical_asset_id=provider_code,
            metric_name=metric_code,
            value=_decimal(selected.get("value")),
            unit="series",
            currency=None,
            period_start=period,
            period_end=period,
            provider_available_at=datetime.combine(period, datetime.min.time(), UTC),
            provider=self.provider,
            provenance_id=_provenance_id(self.provider, metric_code, selected.get("date")),
            response=fact_envelope(self.provider, provider_code, metric_code, endpoint),
        )
