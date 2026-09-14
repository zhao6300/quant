from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.assets import AssetIdentity

MARKETS = ["A_SHARE", "HONG_KONG", "UNITED_STATES"]
ASSET_TYPES = ["EQUITY", "ETF", "OPEN_END_FUND"]


@given(
    repeat_count=st.integers(min_value=1, max_value=5),
    market=st.sampled_from(MARKETS),
    asset_type=st.sampled_from(ASSET_TYPES),
    exchange=st.text(min_size=1, max_size=63).filter(lambda value: value.strip()),
    local_code=st.text(min_size=1, max_size=63).filter(lambda value: value.strip()),
)
def test_canonical_identity_is_idempotent_and_discriminating(
    repeat_count: int,
    market: str,
    asset_type: str,
    exchange: str,
    local_code: str,
) -> None:
    identity = AssetIdentity(market=market, asset_type=asset_type, exchange=exchange, local_code=local_code)

    identities = [identity] + [identity for _ in range(repeat_count)]
    canonical_ids = {item.canonical_id for item in identities}

    assert len(canonical_ids) == 1

    for changed_component in range(4):
        components = [market, asset_type, exchange, local_code]
        changed_value = [
            "OTHER_MARKET" if market != "OTHER_MARKET" else "HONG_KONG",
            "EQUITY" if asset_type != "EQUITY" else "ETF",
            f"{exchange}-1",
            f"{local_code}#",
        ][changed_component]
        changed_components = components.copy()
        changed_components[changed_component] = changed_value
        changed_identity = AssetIdentity(*changed_components)
        assert changed_identity.canonical_id != identity.canonical_id
