from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from mmqp.adapters.data_connectors.base import DailyBarConnector, NormalizedDailyBar
from mmqp.application.ingestion import DataIngestionService
from mmqp.domain.ingestion import DailyBar, DataVersion
from mmqp.domain.providers import ProviderCategorizedError

CONNECTED_DAILY_BAR_SOURCES: tuple[str, ...] = ("stooq", "yahoo-finance")


@dataclass(frozen=True, slots=True)
class SourceDailyBarCommand:
    source_id: str
    market: str
    exchange: str
    canonical_asset_id: str
    provider_code: str
    trading_date: date


@dataclass(frozen=True, slots=True)
class DailyBarSourceIngest:
    dataset: str
    source_id: str
    version: DataVersion
    observation: NormalizedDailyBar
    canonical_asset_id: str
    provider_code: str


class SourceDailyBarIngestionService:
    def __init__(self, connectors: Mapping[str, DailyBarConnector], ingestion: DataIngestionService) -> None:
        self._connectors = dict(connectors)
        self._ingestion = ingestion

    def ingest(self, request: SourceDailyBarCommand) -> DailyBarSourceIngest:
        connector = self._connectors.get(request.source_id)
        if connector is None:
            raise ProviderCategorizedError(
                category="unavailable",
                provider_name=request.source_id,
                request_category="daily-bar",
                status=404,
                retry="never",
            )
        normalized = connector.fetch(
            provider_code=request.provider_code,
            trading_date=request.trading_date,
        )
        observation = self._observation(request, normalized)
        version = self._ingestion.ingest_daily_bar(observation, request.market, request.exchange)
        return DailyBarSourceIngest(
            dataset="DAILY_BAR",
            source_id=request.source_id,
            version=version,
            observation=normalized,
            canonical_asset_id=request.canonical_asset_id,
            provider_code=request.provider_code,
        )

    @staticmethod
    def _observation(
        request: SourceDailyBarCommand,
        normalized: NormalizedDailyBar,
    ) -> DailyBar:
        return DailyBar(
            canonical_asset_id=request.canonical_asset_id,
            trading_date=normalized.trading_date,
            open=normalized.open,
            high=normalized.high,
            low=normalized.low,
            close=normalized.close,
            volume=normalized.volume,
            turnover=normalized.turnover,
            trading_currency=normalized.trading_currency,
            provider_available_at=normalized.provider_available_at,
            retrieved_at=normalized.retrieved_at,
            provider=normalized.provider,
            provider_code=request.provider_code,
            provenance_id=normalized.provenance_id,
        )
