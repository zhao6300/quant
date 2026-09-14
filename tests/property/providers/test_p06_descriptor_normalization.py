from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.application.compliance import ComplianceProfileCommandV1, ComplianceService
from mmqp.application.providers import ProviderAdapterService
from mmqp.domain.compliance import ComplianceProfileVersionV1
from mmqp.domain.market_rules import MarketRuleProfile
from mmqp.domain.providers import (
    AdapterCapabilitiesV1,
    ProviderAdapterRegistration,
    ProviderRequestLimitsV1,
)

PROVIDERS = ("provider-a", "provider-b", "provider-c")
CREDIENTIAL_ACCOUNT_TYPES = ("research", "academic", "personal")
CATEGORIES = ("daily-bar", "fund-nav", "fundamental-fact")
CATEGORIES_IMPLEMENTED = ("daily-bar", "fund-nav", "fundamental-fact")
CATESTIMATE_WAIT = 12


def _profile(version_id: str) -> MarketRuleProfile:
    return MarketRuleProfile(
        version_id=version_id,
        market="A_SHARE",
        exchange="SSE",
        asset_type="EQUITY",
        effective_from=date(2025, 1, 1),
        effective_to=None,
        trading_lot=100,
        tick_size=Decimal("0.01"),
        price_limit_rule="STATIC_PERCENTAGE_BASE_REFERENCE",
        price_limit_percent=Decimal("0.10"),
        sell_availability_rule="NEXT_OPEN_MARKET_DATE",
        security_settlement_open_dates=1,
        cash_settlement_open_dates=1,
        permitted_session_types=("regular",),
    )


@given(
    max_requests=st.integers(min_value=1, max_value=1_000_000),
    period_seconds=st.integers(min_value=1, max_value=86_400),
    capability_state=st.sampled_from(("supported", "unsupported", "unknown")),
)
@settings(max_examples=24, deadline=None)
def test_adapter_descriptor_normalizes_omitted_capabilities_and_limits(
    max_requests: int,
    period_seconds: int,
    capability_state: str,
) -> None:
    capabilities = AdapterCapabilitiesV1(contract_version="1.0")
    assert capabilities.authentication_references == ("unknown",)
    assert capabilities.markets == ("unknown",)
    assert capabilities.asset_types == ("unknown",)
    assert capabilities.categories == ("unknown",)
    assert capabilities.update_frequencies == ("unknown",)
    assert capabilities.available_from is None
    assert capabilities.available_to is None
    assert capabilities.request_limits is None

    capabilities = replace(
        capabilities,
        normalized_response=capability_state,
        provenance=capability_state,
        categorized_errors=capability_state,
        request_limits=ProviderRequestLimitsV1(
            max_requests_per_period=max_requests,
            measurement_period_seconds=period_seconds,
        ),
    )
    service = ProviderAdapterService()
    status = service.register(
        ProviderAdapterRegistration(
            adapter_id="provider-a",
            provider_name="Provider A",
            capabilities=capabilities,
        ),
    )

    assert status.capabilities == capabilities
    assert status.capabilities.request_limits is not None
    assert status.capabilities.request_limits == ProviderRequestLimitsV1(
        max_requests_per_period=max_requests,
        measurement_period_seconds=period_seconds,
    )
    assert capability_state in {"supported", "unsupported", "unknown"}


@given(
    provider=st.sampled_from(PROVIDERS),
    category=st.sampled_from(CATEGORIES),
    first_retention=st.booleans(),
    first_export=st.booleans(),
    second_retention=st.booleans(),
    second_export=st.booleans(),
    first_offset_seconds=st.integers(min_value=-86_399, max_value=86_399),
    second_offset_seconds=st.integers(min_value=-86_399, max_value=86_399),
)
@settings(max_examples=24, deadline=None)
def test_compliance_successor_is_complete_and_predecessor_is_immutable(
    provider: str,
    category: str,
    first_retention: bool,
    first_export: bool,
    second_retention: bool,
    second_export: bool,
    first_offset_seconds: int,
    second_offset_seconds: int,
) -> None:
    first_confirmed_at = datetime(
        2024,
        1,
        1,
        12,
        0,
        0,
        tzinfo=timezone(timedelta(seconds=first_offset_seconds)),
    )
    second_confirmed_at = datetime(
        2024,
        2,
        1,
        12,
        0,
        0,
        tzinfo=timezone(timedelta(seconds=second_offset_seconds)),
    )
    repository = _Repository()
    service = ComplianceService(repository)

    first = service.configure_profile(
        ComplianceProfileCommandV1(
            provider_name=provider,
            account_type="research",
            data_categories=(category,),
            permitted_purposes=("academic-research",),
            retention_permissions={category: first_retention},
            export_permissions={category: first_export},
            confirmed_at=first_confirmed_at,
        ),
    )
    second = service.configure_profile(
        ComplianceProfileCommandV1(
            provider_name=provider,
            account_type="research",
            data_categories=(category,),
            permitted_purposes=("policy-research",),
            retention_permissions={category: second_retention},
            export_permissions={category: second_export},
            confirmed_at=second_confirmed_at,
        ),
    )

    assert first.provider_name == provider
    assert first.account_type == "research"
    assert first.data_categories == (category,)
    assert first.permitted_purposes == ("academic-research",)
    assert first.retention_permissions == {category: first_retention}
    assert first.export_permissions == {category: first_export}
    assert first.confirmed_at == first_confirmed_at
    assert first.predecessor_id is None
    assert first.version_id != ""

    assert second.provider_name == provider
    assert second.account_type == "research"
    assert second.data_categories == (category,)
    assert second.permitted_purposes == ("policy-research",)
    assert second.retention_permissions == {category: second_retention}
    assert second.export_permissions == {category: second_export}
    assert second.confirmed_at == second_confirmed_at
    assert second.predecessor_id == first.version_id
    assert second.version_id != first.version_id

    assert first == repository.saved[0]
    assert second == repository.saved[1]
    assert len(repository.saved) == 2
    assert repository.get_current(provider) == second
    assert repository.get_current("other-provider") is None


def datetime_with_offset(base: datetime, offset_seconds: int) -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(seconds=offset_seconds)))


class _Repository:
    def __init__(self) -> None:
        self.saved: list[ComplianceProfileVersionV1] = []

    def get_current(self, provider_name: str) -> ComplianceProfileVersionV1 | None:
        matching = [item for item in self.saved if item.provider_name == provider_name]
        return matching[-1] if matching else None

    def save_profile(self, profile: ComplianceProfileVersionV1) -> None:
        self.saved.append(profile)
