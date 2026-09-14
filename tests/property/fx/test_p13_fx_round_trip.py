from datetime import UTC, date, datetime
from decimal import Decimal, getcontext

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.fx import FXPolicy, FXRate
from mmqp.kernels.fx import convert


def _direct_rate(rate_value: Decimal) -> FXRate:
    return FXRate(
        version_id=f"fx-{rate_value}",
        source_currency="EUR",
        target_currency="USD",
        rate_date=date(2024, 5, 1),
        rate=rate_value,
        provider="PROVIDER",
        provider_pair="EUR/USD",
        retrieved_at=datetime(2024, 5, 1, 12, tzinfo=UTC),
        provenance_id="provenance-1",
        data_version_id="fx-data-1",
    )


def _derive_inverse(rate: FXRate) -> FXRate:
    return FXRate(
        version_id=f"{rate.version_id}-inverse",
        source_currency=rate.target_currency,
        target_currency=rate.source_currency,
        rate_date=rate.rate_date,
        rate=Decimal(1) / rate.rate,
        provider=rate.provider,
        provider_pair=rate.provider_pair,
        retrieved_at=rate.retrieved_at,
        provenance_id=rate.provenance_id,
        data_version_id=rate.data_version_id,
        direct_source_version_id=rate.version_id,
    )


def _policy() -> FXPolicy:
    return FXPolicy("USD", "EXACT_DATE")


@given(
    rate_value=st.decimals(min_value=Decimal("1e-12"), max_value=Decimal("1e12")),
    source_value=st.decimals(min_value=Decimal("0.00000001"), max_value=Decimal("999999999999.99999999")),
)
def test_fx_direct_inverse_round_trip(rate_value: Decimal, source_value: Decimal) -> None:
    getcontext().prec = 50
    direct = _direct_rate(rate_value)
    inverse = _derive_inverse(direct)
    conversion = convert(
        source_value,
        "EUR",
        (direct,),
        date(2024, 5, 1),
        _policy(),
    )
    assert conversion is not None
    assert inverse.rate == Decimal(1) / direct.rate
    assert inverse.direct_source_version_id == direct.version_id
    assert conversion.rate_version_id == direct.version_id
    assert conversion.rate_date == date(2024, 5, 1)
    assert conversion.converted_value == source_value * direct.rate
    if inverse.rate == direct.rate:
        assert inverse.rate == Decimal(1)
