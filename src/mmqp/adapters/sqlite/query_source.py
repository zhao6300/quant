from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, time
from typing import Any

from mmqp.adapters.sqlite.asset_repository import SqliteAssetRegistryRepository
from mmqp.adapters.sqlite.calendars import (
    SqliteTradingCalendarRepository,
    SqliteValuationCalendarRepository,
)
from mmqp.adapters.sqlite.corporate_actions import SqliteCorporateActionRepository
from mmqp.adapters.sqlite.data_versions import SqliteDataVersionRepository
from mmqp.adapters.sqlite.market_rules import SqliteMarketRuleRepository
from mmqp.application.queries import LIVE_SNAPSHOT_ID, QuerySource
from mmqp.domain.assets import AssetVersion
from mmqp.domain.calendars import TradingCalendarVersion, ValuationCalendarVersion
from mmqp.domain.corporate_actions import CorporateActionVersion
from mmqp.domain.ingestion import DailyBar, DataVersion, FundNav
from mmqp.domain.market_rules import MarketRuleProfile


class SqliteQuerySource(QuerySource):
    def __init__(self, database: str) -> None:
        super().__init__([LIVE_SNAPSHOT_ID])
        self._asset_repository = SqliteAssetRegistryRepository(database)
        self._data_repository = SqliteDataVersionRepository(database)
        self._trading_calendar_repository = SqliteTradingCalendarRepository(database)
        self._valuation_calendar_repository = SqliteValuationCalendarRepository(database)
        self._market_rule_repository = SqliteMarketRuleRepository(database)
        self._corporate_action_repository = SqliteCorporateActionRepository(database)

    def records(self, snapshot_id: str, dataset: str) -> tuple[Mapping[str, Any], ...]:
        if snapshot_id != LIVE_SNAPSHOT_ID:
            return ()
        records: list[Mapping[str, Any]]
        if dataset == "ASSET_MASTER":
            records = [self._asset_row(record) for record in self._asset_repository.current()]
        elif dataset == "TRADING_CALENDAR":
            records = [
                self._trading_calendar_row(record) for record in self._trading_calendar_repository.list()
            ]
        elif dataset == "MARKET_RULE_PROFILE":
            records = [self._market_rule_row(record) for record in self._market_rule_repository.list()]
        elif dataset == "VALUATION_CALENDAR":
            records = [
                self._valuation_calendar_row(record) for record in self._valuation_calendar_repository.list()
            ]
        elif dataset == "CORPORATE_ACTION":
            records = [
                self._corporate_action_row(record) for record in self._corporate_action_repository.list()
            ]
        else:
            observations = [
                record for record in self._data_repository.current_observations() if record.dataset == dataset
            ]
            records = [self._observation_row(dataset, record) for record in observations]
        return tuple(records)

    @staticmethod
    def _asset_row(record: AssetVersion) -> dict[str, Any]:
        return {
            "canonical_asset_id": record.asset_id,
            "version_id": record.version_id,
            "asset_type": record.identity.asset_type,
            "market": record.identity.market,
            "exchange": record.identity.exchange,
            "local_code": record.identity.local_code,
            "name": record.name,
            "trading_currency": record.trading_currency,
            "lifecycle_status": record.lifecycle_status,
            "effective_from": record.effective_from,
            "effective_to": record.effective_to,
            "observation_date": record.effective_from,
            "currency": record.trading_currency,
            "data_provenance": "asset-registry",
            "data_quality_status": "VALID",
            "date_semantics": "effective_from/effective_to",
            "snapshot_id": LIVE_SNAPSHOT_ID,
            "warnings": [],
        }

    @staticmethod
    def _trading_calendar_row(record: TradingCalendarVersion) -> dict[str, Any]:
        return {
            "canonical_asset_id": None,
            "version_id": record.version_id,
            "market": record.market,
            "exchange": record.exchange,
            "timezone": record.timezone,
            "effective_from": record.effective_from,
            "effective_to": record.effective_to,
            "observation_date": record.effective_from,
            "available_at": datetime.combine(record.effective_from, time.min, tzinfo=UTC),
            "currency": None,
            "data_provenance": "local-trading-calendar",
            "data_quality_status": "VALID",
            "date_semantics": "effective_from/effective_to",
            "snapshot_id": LIVE_SNAPSHOT_ID,
            "warnings": [],
            "days": list(record.days),
        }

    @staticmethod
    def _valuation_calendar_row(version: ValuationCalendarVersion) -> dict[str, Any]:
        return {
            "canonical_asset_id": None,
            "version_id": version.version_id,
            "market": version.market,
            "timezone": version.timezone,
            "effective_from": version.effective_from,
            "effective_to": version.effective_to,
            "observation_date": version.effective_from,
            "available_at": datetime.combine(version.effective_from, time.min, tzinfo=UTC),
            "currency": None,
            "data_provenance": "local-valuation-calendar",
            "data_quality_status": "VALID",
            "date_semantics": "effective_from/effective_to",
            "snapshot_id": LIVE_SNAPSHOT_ID,
            "warnings": [],
        }

    @staticmethod
    def _market_rule_row(record: MarketRuleProfile) -> dict[str, Any]:
        return {
            "canonical_asset_id": None,
            "version_id": record.version_id,
            "market": record.market,
            "exchange": record.exchange,
            "asset_type": record.asset_type,
            "effective_from": record.effective_from,
            "effective_to": record.effective_to,
            "observation_date": record.effective_from,
            "available_at": datetime.combine(record.effective_from, time.min, tzinfo=UTC),
            "currency": None,
            "data_provenance": "local-market-rules",
            "data_quality_status": "VALID",
            "date_semantics": "effective_from/effective_to",
            "snapshot_id": LIVE_SNAPSHOT_ID,
            "warnings": [],
            "trading_lot": record.trading_lot,
            "tick_size": record.tick_size,
            "price_limit_rule": record.price_limit_rule,
            "sell_availability_rule": record.sell_availability_rule,
        }

    @staticmethod
    def _corporate_action_row(action: CorporateActionVersion) -> dict[str, Any]:
        return {
            "canonical_asset_id": action.canonical_asset_id,
            "version_id": action.version_id,
            "event_id": action.event_id,
            "action_type": action.action_type,
            "announcement_date": action.announcement_date,
            "ex_date": action.ex_date,
            "record_date": action.record_date,
            "effective_date": action.effective_date,
            "terms": {key: value for key, value in action.terms.items()},
            "observation_date": action.ex_date,
            "available_at": datetime.combine(action.ex_date, time.min, tzinfo=UTC),
            "currency": action.terms.get("currency"),
            "provider": "local-corporate-actions",
            "provenance_id": action.provenance_id,
            "data_provenance": action.provenance_id,
            "data_quality_status": "VALID",
            "date_semantics": "announcement/ex/effective",
            "snapshot_id": LIVE_SNAPSHOT_ID,
            "warnings": [],
        }

    @staticmethod
    def _observation_row(dataset: str, record: DataVersion) -> dict[str, Any]:
        observation = record.observation
        if isinstance(observation, DailyBar):
            currency: str | None = observation.trading_currency
        elif isinstance(observation, FundNav):
            currency = observation.pricing_currency
        else:
            currency = observation.currency
        return {
            "canonical_asset_id": record.canonical_asset_id,
            "observation_date": record.logical_date,
            "available_at": observation.provider_available_at,
            "version_id": record.version_id,
            "logical_key": record.logical_key,
            "currency": currency,
            "provider": observation.provider,
            "provenance_id": observation.provenance_id,
            "data_provenance": observation.provenance_id,
            "data_quality_status": "VALID",
            "date_semantics": dataset,
            "snapshot_id": LIVE_SNAPSHOT_ID,
            "warnings": [],
            "observation": observation,
        }
