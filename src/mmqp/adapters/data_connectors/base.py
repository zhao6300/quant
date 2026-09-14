from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from mmqp.domain.providers import ProviderResponseEnvelopeV1


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedDailyBar:
    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Decimal
    trading_currency: str
    provider_available_at: datetime
    retrieved_at: datetime
    provider: str
    provider_code: str
    provenance_id: str
    response: ProviderResponseEnvelopeV1


class DailyBarConnector(ABC):
    @property
    @abstractmethod
    def provider(self) -> str: ...

    @abstractmethod
    def fetch(self, provider_code: str, trading_date: date) -> NormalizedDailyBar: ...
