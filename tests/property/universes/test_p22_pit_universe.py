from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.application.universes import select_universe_history
from mmqp.domain.universes import LiquidityInput, UniverseMembership

# Feature: multi-market quant platform, Property 22.


@settings(max_examples=20, deadline=None)
@given(first_start=st.dates(), first_end=st.dates(), decision_hour=st.integers(0, 23))
def test_p22_universes_use_only_unambiguous_pit_data(
    first_start: date,
    first_end: date,
    decision_hour: int,
) -> None:
    membership_start = min(first_start, first_end)
    membership_end = max(first_start, first_end)
    member = UniverseMembership(
        membership_id="member-1",
        universe_version="universe-v1",
        canonical_asset_id="ASSET-A",
        effective_from=membership_start,
        effective_to=membership_end,
        membership_source="MASTER",
        source_version="source-1",
    )
    decision_at = datetime(
        membership_start.year,
        membership_start.month,
        membership_start.day,
        decision_hour,
        tzinfo=UTC,
    )
    future_liquidity = LiquidityInput(
        input_version_id="future-input",
        canonical_asset_id="ASSET-A",
        available_at=decision_at + timedelta(hours=1),
        value=None,
    )
    result = select_universe_history(
        [member],
        "universe-v1",
        [membership_start],
        decision_at=decision_at,
        liquidity=[future_liquidity],
    )
    assert result.included == ()
    assert result.member_count == 0
    assert result.excluded[0].reason == "LIQUIDITY"
    assert result.decision_at == decision_at
    assert len(result.lookahead_preventions) == 1
    assert result.lookahead_preventions[0].decision_at == decision_at
