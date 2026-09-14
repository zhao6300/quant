from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from mmqp.domain.ingestion import (
    DailyBar,
    DatasetType,
    DataVersion,
    FactSelection,
    FundamentalFact,
    FundNav,
    IncrementalSegment,
    IngestionValidationError,
    validate_daily_bar,
    validate_fund_nav,
    validate_fundamental_fact,
)
from mmqp.ports.calendars import TradingCalendarRepository, ValuationCalendarRepository
from mmqp.ports.data_versions import DataVersionRepository


def _maximal_segments(dates: list[date]) -> tuple[IncrementalSegment, ...]:
    output: list[IncrementalSegment] = []
    for value in sorted(set(dates)):
        if output and value == output[-1].end_date + timedelta(days=1):
            output[-1] = IncrementalSegment(start_date=output[-1].start_date, end_date=value)
        else:
            output.append(IncrementalSegment(start_date=value, end_date=value))
    return tuple(output)


class DataIngestionService:
    """Validate normalized records and drive deterministic revision publication."""

    def __init__(
        self,
        repository: DataVersionRepository,
        trading_repository: TradingCalendarRepository,
        valuation_repository: ValuationCalendarRepository,
    ) -> None:
        self._repository = repository
        self._trading_repository = trading_repository
        self._valuation_repository = valuation_repository

    def ingest_daily_bar(self, observation: DailyBar, market: str, exchange: str) -> DataVersion:
        self._validate_daily_bar(observation)
        self._market_calendar(market, exchange, observation.trading_date)
        return self._repository.publish(observation)

    def ingest_fund_nav(self, observation: FundNav, market: str) -> DataVersion:
        current = self._repository.current_version(
            "FUND_NAV", observation.canonical_asset_id, observation.valuation_date
        )
        self._validate_fund_nav(
            observation,
            None if current is None else getattr(current.observation, "unit_nav", None),
        )
        self._valuation_calendar(market, observation.valuation_date)
        return self._repository.publish(observation)

    def ingest_fundamental_fact(self, observation: FundamentalFact) -> FundamentalFact:
        self._validate_fundamental_fact(observation)
        return observation

    def select_fact(self, observation: FundamentalFact, decision_at: datetime) -> FactSelection:
        return self._repository.select_fact(
            observation.canonical_asset_id,
            observation.metric_name,
            observation.reporting_period_start,
            observation.reporting_period_end,
            decision_at,
        )

    def fact_revisions(self, observation: FundamentalFact) -> list[DataVersion]:
        return self._repository.fact_history(
            observation.canonical_asset_id,
            observation.metric_name,
            observation.reporting_period_start,
            observation.reporting_period_end,
        )

    def increment_segments(
        self,
        dataset: DatasetType,
        canonical_asset_id: str,
        expected_dates: tuple[date, ...],
    ) -> tuple[IncrementalSegment, ...]:
        missing = [
            expected_date
            for expected_date in expected_dates
            if self._repository.current_version(dataset, canonical_asset_id, expected_date) is None
        ]
        return _maximal_segments(missing)

    def _market_calendar(self, market: str | None, exchange: str | None, date_value: date) -> None:
        if market is None or exchange is None:
            raise IngestionValidationError(["calendar"])
        versions = self._trading_repository.select(market, exchange, date_value)
        if len(versions) != 1 or not any(
            day.date == date_value and day.kind != "closed" for day in versions[0].days
        ):
            raise IngestionValidationError(["calendar"])

    def _valuation_calendar(self, market: str | None, date_value: date) -> None:
        if market is None:
            raise IngestionValidationError(["calendar"])
        versions = self._valuation_repository.select(market, date_value)
        if len(versions) != 1:
            raise IngestionValidationError(["calendar"])

    def _validate_daily_bar(self, observation: DailyBar) -> None:
        validate_daily_bar(observation)

    def _validate_fund_nav(self, observation: FundNav, current_unit_nav: Decimal | None = None) -> None:
        validate_fund_nav(observation, current_unit_nav)

    def _validate_fundamental_fact(self, observation: FundamentalFact) -> FundamentalFact:
        validate_fundamental_fact(observation)
        return observation
