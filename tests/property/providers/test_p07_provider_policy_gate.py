from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.application.market_rules import MarketRuleService
from tests.property.providers.test_p06_descriptor_normalization import _profile


@given(
    version_id=st.sampled_from(("profile-a", "profile-b")),
)
@settings(max_examples=30, deadline=None)
def test_market_rule_profile_is_consistent(version_id: str) -> None:
    service = MarketRuleService()
    service.validate(_profile(version_id))
    service.register(_profile(version_id))
