import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from mmqp.adapters.sqlite.data_versions import SqliteDataVersionRepository
from mmqp.application.ingestion import DataIngestionService
from mmqp.domain.calendars import (
    TradingCalendarDay,
    TradingCalendarVersion,
    TradingSession,
    ValuationCalendarVersion,
)
from mmqp.domain.ingestion import DailyBar, FundamentalFact, FundNav, IngestionValidationError


def test_daily_bar_reuses_equal_version_and_appends_changed_version(database: str) -> None:
    repository = SqliteDataVersionRepository(database)
    ingested = _service(repository).ingest_daily_bar(daily_bar(), "US", "NYSE")
    reused = _service(repository).ingest_daily_bar(daily_bar(), "US", "NYSE")
    successor = _service(repository).ingest_daily_bar(daily_bar("11"), "US", "NYSE")

    assert reused.version_id == ingested.version_id
    assert successor.revision_position == ingested.revision_position + 1
    assert successor.predecessor_id == ingested.version_id
    current = repository.current_version("DAILY_BAR", "ASSET", date(2024, 3, 1))
    assert current is not None
    assert current.content_id == successor.content_id


def test_invalid_daily_bar_reports_rule_and_preserves_current(database: str) -> None:
    repository = SqliteDataVersionRepository(database)
    ingested = _service(repository).ingest_daily_bar(daily_bar(), "US", "NYSE")
    invalid = DailyBar(
        canonical_asset_id="",
        trading_date=date(2019, 3, 1),
        open=Decimal("0"),
        high=Decimal("1.00000000"),
        low=Decimal("2.00000000"),
        close=Decimal("1.00000000"),
        volume=Decimal("-1"),
        turnover=Decimal("1000.0000000000000000000000000000000000000000000000000000000000000000000000000"),
        trading_currency="US",
        provider_available_at=BASE_TIME.replace(tzinfo=None),
        retrieved_at=BASE_TIME.replace(tzinfo=None),
        provider="",
        provider_code="CODE",
        provenance_id="PROVENANCE",
    )

    with pytest.raises(IngestionValidationError) as errors:
        _service(repository).ingest_daily_bar(invalid, "US", "NYSE")

    assert errors.value.fields == sorted(
        {
            "canonical_asset_id.missing",
            "trading_date.range",
            "open.range",
            "volume.range",
            "high.relationship",
            "low.relationship",
            "trading_currency.currency",
            "provider_available_at.timezone",
            "retrieved_at.timezone",
            "provider.missing",
        }
    )
    current = repository.current_version("DAILY_BAR", "ASSET", date(2024, 3, 1))
    assert current is not None
    assert current.content_id == ingested.content_id


def test_fund_nav_requires_cumulative_nav_to_exceed_unit_nav(database: str) -> None:
    repository = SqliteDataVersionRepository(database)
    with pytest.raises(IngestionValidationError) as errors:
        _service(repository).ingest_fund_nav(fund_nav(cumulative="9"), "FUND")

    assert errors.value.fields == ["cumulative_nav.relationship"]
    assert repository.current_version("FUND_NAV", "FUND", date(2024, 3, 1)) is None


def test_facts_advance_revision_and_reuse_identical_content(database: str) -> None:
    repository = SqliteDataVersionRepository(database)
    original = repository.publish(fact())
    reused = repository.publish(fact())

    assert reused.version_id == original.version_id
    assert reused.revision_position == 1

    revised = fact(revision_version="r2", provider_available_at=BASE_TIME + timedelta(days=1))
    successor = repository.publish(revised)
    duplicate = repository.publish(revised)

    assert successor.revision_position == 2
    assert successor.predecessor_id == original.version_id
    assert duplicate.version_id == successor.version_id
    assert repository.fact_history("ASSET", "revenue", date(2024, 1, 1), date(2024, 3, 31)) == [
        original,
        successor,
    ]


def test_point_in_time_fact_selection_uses_latest_available_at_then_highest_position(
    database: str,
) -> None:
    repository = SqliteDataVersionRepository(database)
    selected_after = repository.publish(fact("r1", BASE_TIME + timedelta(seconds=5)))
    selected_tie = repository.publish(fact("r2", BASE_TIME + timedelta(seconds=5)))
    repository.publish(fact("r3", BASE_TIME + timedelta(seconds=10)))

    selected = repository.select_fact(
        "ASSET",
        "revenue",
        date(2024, 1, 1),
        date(2024, 3, 31),
        BASE_TIME + timedelta(seconds=5),
    )
    before_all = repository.select_fact(
        "ASSET",
        "revenue",
        date(2024, 1, 1),
        date(2024, 3, 31),
        BASE_TIME,
    )

    selected_observation = selected.observation
    assert selected_observation is not None
    assert selected_observation.revision_version == "r2"
    assert selected_observation.provider_available_at == selected_tie.observation.provider_available_at
    repository_facts = repository.fact_history("ASSET", "revenue", date(2024, 1, 1), date(2024, 3, 31))
    assert len(repository_facts) == 3
    assert selected_after.version_id != selected_tie.version_id
    assert selected_after.revision_position == 1
    assert selected_tie.revision_position == 2
    assert before_all.observation is None


BASE_TIME = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)


def trading_calendar() -> TradingCalendarVersion:
    return TradingCalendarVersion(
        version_id="cal-v1",
        market="US",
        exchange="NYSE",
        timezone="UTC",
        effective_from=date(2024, 1, 1),
        effective_to=None,
        days=(
            TradingCalendarDay(
                market="US",
                exchange="NYSE",
                date=date(2024, 3, 1),
                kind="full",
                sessions=(TradingSession(start="09:00", end="16:00", kind="regular"),),
            ),
        ),
    )


def valuation_calendar() -> ValuationCalendarVersion:
    return ValuationCalendarVersion(
        version_id="valuation-v1",
        market="FUND",
        timezone="UTC",
        effective_from=date(2024, 1, 1),
        effective_to=None,
    )


class FixedTradingCalendarRepository:
    def select(self, market: str, exchange: str, as_of: date) -> list[TradingCalendarVersion]:
        del market, exchange, as_of
        return [trading_calendar()]


class FixedValuationCalendarRepository:
    def select(self, market: str, as_of: date) -> list[ValuationCalendarVersion]:
        del market, as_of
        return [valuation_calendar()]


def daily_bar(
    value: str = "10.2500",
    provider_available_at: datetime = BASE_TIME,
) -> DailyBar:
    return DailyBar(
        canonical_asset_id="ASSET",
        trading_date=date(2024, 3, 1),
        open=Decimal("9.8000"),
        high=Decimal("11.5000"),
        low=Decimal("9.5000"),
        close=Decimal(value),
        volume=Decimal("1000"),
        turnover=Decimal("11000"),
        trading_currency="USD",
        provider_available_at=provider_available_at,
        retrieved_at=BASE_TIME,
        provider="PROVIDER",
        provider_code="CODE",
        provenance_id="PROVENANCE",
    )


def fund_nav(unit: str = "10.000000", cumulative: str = "11.000000") -> FundNav:
    return FundNav(
        canonical_asset_id="FUND",
        valuation_date=date(2024, 3, 1),
        unit_nav=Decimal(unit),
        cumulative_nav=None if cumulative is None else Decimal(cumulative),
        pricing_currency="JPY",
        provider_available_at=BASE_TIME,
        retrieved_at=BASE_TIME,
        provider="PROVIDER",
        provider_code="CODE",
        provenance_id="PROVENANCE",
    )


def fact(
    revision_version: str = "r1",
    provider_available_at: datetime = BASE_TIME,
) -> FundamentalFact:
    return FundamentalFact(
        canonical_asset_id="ASSET",
        metric_name="revenue",
        value=Decimal("100"),
        unit="USD",
        currency="USD",
        reporting_period_start=date(2024, 1, 1),
        reporting_period_end=date(2024, 3, 31),
        announcement_at=BASE_TIME,
        provider_available_at=provider_available_at,
        provider="PROVIDER",
        revision_version=revision_version,
        provenance_id="PROVENANCE",
    )


class _FakeTradingCalendarRepository:
    def select(self, market: str, exchange: str, as_of: date) -> list[TradingCalendarVersion]:
        return [trading_calendar()]

    def create(self, version: TradingCalendarVersion) -> TradingCalendarVersion:
        return version

    def list(self, market: str | None = None, exchange: str | None = None) -> list[TradingCalendarVersion]:
        del market, exchange
        return [trading_calendar()]

    def close(self) -> None:
        return None


class _FakeValuationCalendarRepository:
    def select(self, market: str, as_of: date) -> list[ValuationCalendarVersion]:
        del market, as_of
        return [valuation_calendar()]

    def create(self, version: ValuationCalendarVersion) -> ValuationCalendarVersion:
        return version

    def list(self, market: str | None = None) -> list[ValuationCalendarVersion]:
        del market
        return [valuation_calendar()]

    def close(self) -> None:
        return None


def _service(repository: SqliteDataVersionRepository) -> DataIngestionService:
    return DataIngestionService(
        repository, _FakeTradingCalendarRepository(), _FakeValuationCalendarRepository()
    )


@pytest.fixture
def database(tmp_path: str) -> str:
    return os.path.join(str(tmp_path), "ingestion.sqlite3")
