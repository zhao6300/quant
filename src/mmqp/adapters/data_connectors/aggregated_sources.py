from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from mmqp.adapters.data_connectors.base import DailyBarConnector, NormalizedDailyBar
from mmqp.adapters.data_connectors.normalize import _provenance_id
from mmqp.adapters.data_connectors.provider_response import envelope


class _SourceConnector(DailyBarConnector):
    def __init__(self, provider: str, endpoint: str) -> None:
        self._provider = provider
        self._endpoint = endpoint

    @property
    def provider(self) -> str:
        return self._provider

    def request_blueprint(self, provider_code: str, trading_date: date) -> Mapping[str, Any]:
        return {
            "url": self._endpoint,
            "provider_code": provider_code,
            "trading_date": trading_date.isoformat(),
        }

    def row(self, provider_code: str, trading_date: date) -> Mapping[str, Any]:
        raise NotImplementedError

    def fetch(self, provider_code: str, trading_date: date) -> NormalizedDailyBar:
        row = self.row(provider_code, trading_date)
        return self._bar(provider_code, row, trading_date)

    def _bar(self, provider_code: str, row: Mapping[str, Any], trading_date: date) -> NormalizedDailyBar:
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
            provider=self.provider,
            provider_code=provider_code,
            provenance_id=_provenance_id(self.provider, provider_code, trading_date),
            response=envelope(self.provider, provider_code, self._endpoint, source_version="catalog-v1"),
        )


@dataclass(frozen=True, slots=True)
class AkShareDailyBarConnector(_SourceConnector):
    @property
    def provider(self) -> str:
        return "akshare"

    def request_blueprint(self, provider_code: str, trading_date: date) -> Mapping[str, Any]:
        return {
            **super().request_blueprint(provider_code, trading_date),
            "function": "stock_zh_a_hist",
        }
