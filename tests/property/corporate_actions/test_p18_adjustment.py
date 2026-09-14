from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.application.corporate_actions import _validate
from mmqp.domain.corporate_actions import CorporateActionVersion


@settings(max_examples=8, deadline=None)
@given(
    action_type=st.sampled_from(["DIVIDEND", "SPLIT", "MERGER", "SPINOFF"]),
    ex_date=st.dates(),
)
def test_corporate_action_validation(action_type: str, ex_date: object) -> None:
    _validate(_corporate_action(action_type, ex_date))


def _corporate_action(action_type: str, ex_date: object) -> CorporateActionVersion:
    return CorporateActionVersion(
        canonical_asset_id="ASSET",
        event_id="event-id",
        action_type=action_type,
        terms={"amount": "1.00", "currency": "USD"},
        provenance_id="PROVENANCE",
        version_id="v1",
        announcement_date=ex_date,
        ex_date=ex_date,
        record_date=None,
        effective_date=ex_date,
    )
