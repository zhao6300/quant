from datetime import UTC, datetime
from typing import Literal

import pytest

from mmqp.adapters.http_provider.base import ProviderHTTPClient
from mmqp.application.providers import ProviderAdapterService
from mmqp.domain.providers import (
    AdapterCapabilitiesV1,
    ProviderAdapterRegistration,
    ProviderCapabilityError,
    ProviderCategorizedError,
    ProviderNormalizedResponseV1,
    ProviderRequest,
    ProviderRequestLimitsV1,
    ProviderResponseEnvelopeV1,
)

CAPABILITY_VECTORS: tuple[str, ...] = ("vec-complete", "vec-omitted")
HTTP_ERROR_VECTORS: tuple[tuple[str, int], ...] = (
    ("throttled", 429),
    ("unavailable", 503),
    ("unavailable", 418),
)
CLIENT_ERROR_VECTORS: tuple[tuple[str, int, str], ...] = (
    ("throttled", 429, "safe_after"),
    ("unavailable", 503, "safe_after"),
    ("unavailable", 418, "safe_after"),
)
CONTRACT_VECTORS: tuple[tuple[str, str, str], ...] = (
    ("with-limits", "1.0", "ok"),
    ("without-limits", "1.0", "ok"),
    ("unknown-normalization", "1.0", "registerable"),
)


def _capabilities(
    contract_version: Literal["1", "1.0"] = "1.0",
    *,
    normalized_response: Literal["supported", "unknown"] = "supported",
) -> AdapterCapabilitiesV1:
    return AdapterCapabilitiesV1(
        contract_version=contract_version,
        normalized_response=normalized_response,
        provenance="supported",
        categorized_errors="supported",
        request_limits=ProviderRequestLimitsV1(
            max_requests_per_period=2,
            measurement_period_seconds=60,
        ),
    )


def _contract_response_envelope(request: ProviderRequest) -> ProviderResponseEnvelopeV1:
    return ProviderResponseEnvelopeV1(
        provider_name=request.provider_name,
        request_category=request.request_category,
        request_parameters=request.parameters,
        retrieval_time=datetime.now(UTC),
        normalized=ProviderNormalizedResponseV1({"ok": 1}),
    )


def _capabilities_for(vector: str) -> AdapterCapabilitiesV1:
    assert vector in {item[0] for item in CONTRACT_VECTORS}
    contract_version = "1.0"
    request_limits = (
        None
        if vector == "without-limits"
        else ProviderRequestLimitsV1(
            max_requests_per_period=1,
            measurement_period_seconds=60,
        )
    )
    return AdapterCapabilitiesV1(
        contract_version=contract_version,
        normalized_response="supported",
        provenance="supported",
        categorized_errors="supported",
        request_limits=request_limits,
    )


@pytest.mark.parametrize("adapter_id", CAPABILITY_VECTORS)
def test_adapter_status_is_declared_before_enable(adapter_id: str) -> None:
    service = ProviderAdapterService()
    registration = ProviderAdapterRegistration(
        adapter_id=adapter_id,
        provider_name="contract-provider",
        capabilities=_capabilities(),
    )
    status = service.register(registration)
    assert service.display(adapter_id) is status
    enabled = service.enable(adapter_id)
    assert enabled is not status
    assert enabled.enabled is True


def test_adapter_response_has_status() -> None:
    request = ProviderRequest("contract-provider", "daily-bar", {"id": "asset-a"})
    sent: list[ProviderRequest] = []
    transport = ProviderHTTPClient(lambda item: (sent.append(item), _contract_response_envelope(item))[1])
    response = transport.send(request)
    assert response.provider_correlation_id is None
    assert len(sent) == 1


@pytest.mark.parametrize("adapter_id", CAPABILITY_VECTORS)
def test_enable_requires_complete_capability_description(adapter_id: str) -> None:
    service = ProviderAdapterService()
    status = service.register(
        ProviderAdapterRegistration(
            adapter_id=adapter_id,
            provider_name="contract-provider",
            capabilities=_capabilities(),
        )
    )
    assert status.enabled is False


@pytest.mark.parametrize(("category", "status_code"), HTTP_ERROR_VECTORS)
def test_adapter_status_is_categorized(category: str, status_code: int) -> None:
    request = ProviderRequest("contract-provider", "daily-bar", {"id": "asset-a"})
    error = ProviderCategorizedError(
        category=category,
        provider_name=request.provider_name,
        request_category=request.request_category,
        provider_correlation_id=f"offline-{status_code}",
        status=status_code,
    )
    assert error.category == category
    assert error.provider_correlation_id == f"offline-{status_code}"


@pytest.mark.parametrize(
    ("vector", "contract_version", "expected"),
    CONTRACT_VECTORS,
)
def test_reusable_contract_vectors_enforce_registration(
    vector: str,
    contract_version: str,
    expected: str,
) -> None:
    service = ProviderAdapterService()
    capabilities = _capabilities_for(vector)
    assert capabilities.contract_version == contract_version
    registration = ProviderAdapterRegistration(
        adapter_id=vector,
        provider_name="contract-provider",
        capabilities=capabilities,
    )
    if expected == "ok":
        status = service.register(registration)
        assert service.display(vector) is status
        assert service.enable(vector).enabled is True
    elif expected == "incompatible":
        status = service.register(registration)
        assert status.incompatible_reason == "unsupported-contract-version:2.0"
        with pytest.raises(ProviderCapabilityError) as error:
            service.enable(vector)
        assert error.value.fields == ["capabilities"]
    else:
        status = service.register(registration)
        assert vector == "unknown-normalization" and status.incompatible_reason is None


def test_request_limit_boundary_rejects_zero() -> None:
    with pytest.raises(ProviderCapabilityError) as error:
        ProviderAdapterService().register(
            ProviderAdapterRegistration(
                adapter_id="limits",
                provider_name="contract-provider",
                capabilities=AdapterCapabilitiesV1(
                    contract_version="1.0",
                    normalized_response="supported",
                    provenance="supported",
                    categorized_errors="supported",
                    request_limits=ProviderRequestLimitsV1(
                        max_requests_per_period=0,
                        measurement_period_seconds=60,
                    ),
                ),
            )
        )
    assert error.value.fields == ["request_limits"]
