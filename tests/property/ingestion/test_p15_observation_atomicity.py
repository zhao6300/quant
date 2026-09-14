from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st
from pytest import raises

from mmqp.domain.ingestion import (
    DailyBar,
    FundamentalFact,
    FundNav,
    IngestionValidationError,
    validate_daily_bar,
    validate_fund_nav,
    validate_fundamental_fact,
)


@settings(max_examples=8, deadline=None)
@given(
    dataset=st.sampled_from(("DAILY_BAR", "FUND_NAV", "FUNDAMENTAL_FACT")),
    value=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000")),
)
def test_market_observations_validate_and_publish_atomically(dataset: str, value: Decimal) -> None:
    if dataset == "DAILY_BAR":
        with raises(IngestionValidationError):
            validate_daily_bar(_invalid_bar(value))
        validate_daily_bar(_valid_bar(value))
    elif dataset == "FUND_NAV":
        with raises(IngestionValidationError):
            validate_fund_nav(_invalid_fund_nav(value))
        validate_fund_nav(_valid_fund_nav(value))
    else:
        with raises(IngestionValidationError):
            validate_fundamental_fact(_invalid_fact(value))
        validate_fundamental_fact(_valid_fact(value))


def _invalid_bar(value: Decimal) -> DailyBar:
    return DailyBar(
        canonical_asset_id="ASSET",
        trading_date=date(2024, 3, 1),
        open=Decimal("-1"),
        high=value,
        low=value,
        close=value,
        volume=Decimal("-1"),
        turnover=Decimal("1e19"),
        trading_currency="USD",
        provider_available_at=_time(),
        retrieved_at=_time(),
        provider="PROVIDER",
        provider_code="CODE",
        provenance_id="PROVENANCE",
    )


def _valid_bar(value: Decimal) -> DailyBar:
    return DailyBar(
        canonical_asset_id="ASSET",
        trading_date=date(2024, 3, 1),
        open=value,
        high=value,
        low=value,
        close=value,
        volume=Decimal("1000"),
        turnover=Decimal("1000"),
        trading_currency="USD",
        provider_available_at=_time(),
        retrieved_at=_time(),
        provider="PROVIDER",
        provider_code="CODE",
        provenance_id="PROVENANCE",
    )


def _invalid_fund_nav(value: Decimal) -> FundNav:
    return FundNav(
        canonical_asset_id="FUND",
        valuation_date=date(2024, 3, 1),
        unit_nav=value,
        cumulative_nav=value - Decimal(1),
        pricing_currency="USD",
        provider_available_at=_time(),
        retrieved_at=_time(),
        provider="PROVIDER",
        provider_code="CODE",
        provenance_id="PROVENANCE",
    )


def _valid_fund_nav(value: Decimal) -> FundNav:
    return FundNav(
        canonical_asset_id="FUND",
        valuation_date=date(2024, 3, 1),
        unit_nav=value,
        cumulative_nav=value,
        pricing_currency="USD",
        provider_available_at=_time(),
        retrieved_at=_time(),
        provider="PROVIDER",
        provider_code="CODE",
        provenance_id="PROVENANCE",
    )


def _invalid_fact(value: Decimal) -> FundamentalFact:
    return FundamentalFact(
        canonical_asset_id="ASSET",
        metric_name="",
        unit="",
        value=value,
        currency=None,
        reporting_period_start=date(2024, 1, 1),
        reporting_period_end=date(2024, 12, 31),
        announcement_at=_time(),
        provider_available_at=_time(),
        provider="PROVIDER",
        revision_version="r1",
        provenance_id="PROVENANCE",
    )


def _valid_fact(value: Decimal) -> FundamentalFact:
    return FundamentalFact(
        canonical_asset_id="ASSET",
        metric_name="revenue",
        unit="USD",
        value=value,
        currency="USD",
        reporting_period_start=date(2024, 1, 1),
        reporting_period_end=date(2024, 12, 31),
        announcement_at=_time(),
        provider_available_at=_time(),
        provider="PROVIDER",
        revision_version="r1",
        provenance_id="PROVENANCE",
    )


def _time() -> datetime:
    return datetime(2024, 3, 1, 12, tzinfo=UTC)
