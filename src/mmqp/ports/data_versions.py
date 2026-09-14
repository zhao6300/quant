from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from mmqp.domain.ingestion import (
    DailyBar,
    DatasetType,
    DataVersion,
    FactSelection,
    FundamentalFact,
    FundNav,
)


class DataVersionRepository(Protocol):
    """Persistence port for immutable observation revisions and current files."""

    def publish(
        self,
        observation: DailyBar | FundNav | FundamentalFact,
    ) -> DataVersion: ...

    def current_version(
        self,
        dataset: DatasetType,
        canonical_asset_id: str,
        logical_date: date,
    ) -> DataVersion | None: ...

    def fact_history(
        self,
        canonical_asset_id: str,
        metric_name: str,
        reporting_period_start: date,
        reporting_period_end: date,
    ) -> list[DataVersion]: ...
    def select_fact(
        self,
        canonical_asset_id: str,
        metric_name: str,
        reporting_period_start: date,
        reporting_period_end: date,
        decision_at: datetime,
    ) -> FactSelection: ...
