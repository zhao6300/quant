import pytest

from mmqp.adapters.http_provider.base import MAX_TIMEOUT_SECONDS, ProviderHTTPClient
from mmqp.application.providers import ProviderAdapterService
from mmqp.domain.providers import (
    AdapterCapabilitiesV1,
    ProviderAdapterRegistration,
    ProviderCapabilityError,
    ProviderCategorizedError,
    ProviderRequest,
    ProviderRequestLimitsV1,
)


def _capabilities(contract_version: str = "1.0") -> AdapterCapabilitiesV1:
    return AdapterCapabilitiesV1(
        contract_version=contract_version,
        normalized_response="supported",
        provenance="supported",
        categorized_errors="supported",
        request_limits=ProviderRequestLimitsV1(
            max_requests_per_period=1,
            measurement_period_seconds=1,
        ),
    )


def _registration(contract_version: str = "1.0") -> ProviderAdapterRegistration:
    return ProviderAdapterRegistration(
        adapter_id="provider-a",
        provider_name="Provider A",
        capabilities=_capabilities(contract_version),
    )


def test_capabilities_and_enable_after_display_flow() -> None:
    service = ProviderAdapterService()
    registration = _registration()
    assert isinstance(registration, object) and hasattr(registration, "capabilities")
    status = service.register(registration)
    assert status.capabilities.normalized_response == "supported"
    assert status.capabilities.provenance == "supported"
    assert service.display("provider-a") is status
    assert service.enable("provider-a").enabled is True


def test_request_limit_bounds_are_exact() -> None:
    service = ProviderAdapterService()
    capabilities = _capabilities()
    limits = capabilities.request_limits
    assert limits is not None
    assert limits.max_requests_per_period == 1 and limits.measurement_period_seconds == 1
    service._normalize(capabilities)


def test_unsupported_contract_is_disabled_and_declared() -> None:
    service = ProviderAdapterService()
    status = service.register(_registration("0.9"))
    assert status.enabled is False
    assert status.incompatible_reason == "unsupported-contract-version:0.9"
    with pytest.raises(ProviderCapabilityError) as error:
        service.enable("provider-a")
    assert error.value.problem.kind == "provider/contract-incompatible"


def _request() -> ProviderRequest:
    return ProviderRequest(
        provider_name="Provider A",
        request_category="daily-bars",
        parameters={"asset_id": "asset-a"},
    )


def test_hard_timeout_is_bounded() -> None:
    assert MAX_TIMEOUT_SECONDS == 30
    client = ProviderHTTPClient(lambda _request: [])
    with pytest.raises(ProviderCategorizedError) as error:
        client.send(_request(), timeout_seconds=31)
    assert error.value.category == "policy_blocked"


@pytest.mark.parametrize(
    ("status_code", "category"),
    [(429, "throttled"), (503, "unavailable")],
)
def test_http_statuses_are_categorized(
    status_code: int,
    category: str,
) -> None:
    client = ProviderHTTPClient(
        lambda _request: {"status_code": status_code, "provider_correlation_id": "corr-1"},
    )
    with pytest.raises(ProviderCategorizedError) as error:
        client.send(_request(), timeout_seconds=30)
    assert error.value.category == category
    assert error.value.provider_correlation_id == "corr-1"
