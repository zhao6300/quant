from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from mmqp.adapters.sqlite.fx import SqliteFXRateRepository
from mmqp.application.fx import FXService
from mmqp.domain.fx import (
    FXPolicy,
    FXPolicyError,
    FXRate,
    FXValidationError,
    validate_policy,
    validate_rate,
)


def _direct_rate() -> FXRate:
    return FXRate(
        version_id="direct-1",
        source_currency="EUR",
        target_currency="USD",
        rate_date=date(2024, 5, 1),
        rate=Decimal("1.250000000000000000000000000000000000000000000000000000"),
        provider="PROVIDER",
        provider_pair="EUR/USD",
        retrieved_at=datetime(2024, 5, 1, 12, tzinfo=UTC),
        provenance_id="provenance-1",
        data_version_id="fx-data-1",
    )


@pytest.fixture
def database(tmp_path) -> str:
    return str(tmp_path / "fx.sqlite3")


def test_direct_rate_stores_derived_inverse_with_source_provenance(database: str) -> None:
    direct = _direct_rate()
    stored_direct, inverse = FXService(SqliteFXRateRepository(database)).register_direct(direct)

    assert inverse is not None
    assert inverse.rate == Decimal(1) / direct.rate
    assert inverse.provenance_id == direct.provenance_id
    storage = SqliteFXRateRepository(database)
    direct_rows = storage.select("EUR", "USD", (date(2024, 5, 1),))
    inverse_rows = storage.select("USD", "EUR", (date(2024, 5, 1),))
    assert stored_direct.version_id == "direct-1"
    assert inverse_rows[0].rate == Decimal(1) / direct.rate
    assert inverse_rows[0].direct_source_version_id == direct_rows[0].version_id


def test_storage_preserves_backward_compatibility_preconditions(database: str) -> None:
    repository = SqliteFXRateRepository(database)
    direct = _direct_rate()
    FXService(repository).register_direct(direct)
    stored = repository.select("EUR", "USD", (date(2024, 5, 1),))

    assert stored[0].rate == direct.rate
    assert not hasattr(stored[0], "delete")
    assert not hasattr(stored[0], "update")


def test_policy_rejects_unknown_currencies() -> None:
    policy = FXPolicy("", "LATEST_PRIOR_FALLBACK")

    with pytest.raises(FXPolicyError):
        validate_policy(policy)


def test_rate_validation_reports_invalid_decimal_range() -> None:
    direct = _direct_rate()
    invalid = FXRate(
        version_id=direct.version_id,
        source_currency=direct.source_currency,
        target_currency=direct.target_currency,
        rate_date=direct.rate_date,
        rate=Decimal("1.25e-13"),
        provider=direct.provider,
        provider_pair=direct.provider_pair,
        retrieved_at=direct.retrieved_at,
        provenance_id=direct.provenance_id,
        data_version_id=direct.data_version_id,
    )

    with pytest.raises(FXValidationError):
        validate_rate(invalid)
