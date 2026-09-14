import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from mmqp.adapters.sqlite.compliance import SqliteComplianceRepository
from mmqp.application.compliance import (
    ComplianceProfileCommandV1,
    ComplianceService,
)
from mmqp.application.providers import ProviderAdapterService
from mmqp.domain.compliance import CompliancePolicyError
from mmqp.domain.providers import (
    AdapterCapabilitiesV1,
    ProviderAdapterRegistration,
    ProviderAdapterStatusV1,
    ProviderCategorizedError,
    ProviderRequestLimitsV1,
)
from mmqp.domain.security import CredentialSummary, CredentialUnavailableError, SecureCredential
from tests.fixtures.providers.local_https import LocalHTTPSProvider
from tests.fixtures.providers.provider_adapter import PROVIDER_NAME, LocalHTTPSAdapter

TEST_TIMEOUT: Final[float] = 0.02


def _capabilities() -> AdapterCapabilitiesV1:
    return AdapterCapabilitiesV1(
        contract_version="1.0",
        normalized_response="supported",
        provenance="supported",
        categorized_errors="supported",
        request_limits=ProviderRequestLimitsV1(
            max_requests_per_period=2,
            measurement_period_seconds=60,
        ),
    )


def _registration() -> ProviderAdapterRegistration:
    return ProviderAdapterRegistration(
        adapter_id="local-https",
        provider_name=PROVIDER_NAME,
        capabilities=_capabilities(),
    )


def _credential() -> SecureCredential:
    return SecureCredential(
        CredentialSummary("local-provider", PROVIDER_NAME, os.getuid()),
        (),
        "offline-secret",
    )


def _adapter(provider: LocalHTTPSProvider) -> LocalHTTPSAdapter:
    service = ProviderAdapterService()
    registration = _registration()
    status = service.register(registration)
    assert service.display(status.adapter_id) is status
    enabled = service.enable(status.adapter_id)
    assert enabled.enabled is True

    adapter = LocalHTTPSAdapter(provider)
    adapter.configure_capabilities(
        ProviderAdapterStatusV1(
            adapter_id=registration.adapter_id,
            provider_name=PROVIDER_NAME,
            capabilities=registration.capabilities,
            enabled=True,
        )
    )
    adapter.set_credential(_credential(), os.getuid())
    adapter.enable_after_display()
    return adapter


def test_offline_provider_passes_display_and_capability_gates() -> None:
    provider = LocalHTTPSProvider(timeout_seconds=TEST_TIMEOUT)
    try:
        adapter = _adapter(provider)
        response = adapter.request("/secure/data")
        assert response.provider_name == PROVIDER_NAME
        assert response.normalized.values == {"ok": True}
        assert provider.requests == [("/secure/data", b'{"payload":"offline"}')]
    finally:
        provider.stop()


def test_offline_adapter_requires_capability_before_send() -> None:
    provider = LocalHTTPSProvider(timeout_seconds=TEST_TIMEOUT)
    try:
        adapter = LocalHTTPSAdapter(provider)
        with pytest.raises(ProviderCategorizedError):
            adapter.request("/secure/data")
        assert adapter.sent == []
        assert provider.requests == []
    finally:
        provider.stop()


def test_offline_adapter_credential_unavailable_blocks_send() -> None:
    provider = LocalHTTPSProvider(timeout_seconds=TEST_TIMEOUT)
    try:
        adapter = LocalHTTPSAdapter(provider)
        with pytest.raises(CredentialUnavailableError):
            adapter.credential_manager.retrieve(PROVIDER_NAME, os.getuid())
        assert adapter.sent == []
        assert provider.requests == []
    finally:
        provider.stop()


def test_local_https_scope_rejects_sensitive_request_before_transport() -> None:
    provider = LocalHTTPSProvider(timeout_seconds=TEST_TIMEOUT)
    try:
        assert provider.scope.allows(f"{provider.origin}/secure/data") is True
        assert provider.scope.allows(f"{provider.origin}/public/data") is False
        assert provider.scope.allows("https://local-provider.test:443/secure/data") is False
        assert provider.requests == []
    finally:
        provider.stop()


@pytest.mark.parametrize("mode", ("timeout", "throttled:429", "unavailable:503"))
def test_offline_https_errors_are_categorized(mode: str) -> None:
    provider = LocalHTTPSProvider(timeout_seconds=TEST_TIMEOUT)
    try:
        provider.response_mode = mode
        provider.request("/secure/data", {})
        assert provider.exceptions[-1] == (mode, 1)
    finally:
        provider.stop()


@pytest.mark.parametrize(
    ("retention_allowed", "export_allowed"),
    ((False, True), (True, False), (False, False)),
)
def test_offline_compliance_blocks_prohibited_observation(
    tmp_path: Path,
    retention_allowed: bool,
    export_allowed: bool,
) -> None:
    repository = SqliteComplianceRepository(tmp_path / "compliance.sqlite")
    service = ComplianceService(repository)
    profile = service.configure_profile(
        ComplianceProfileCommandV1(
            provider_name=PROVIDER_NAME,
            account_type="research",
            data_categories=("daily-bar",),
            permitted_purposes=("academic-research",),
            retention_permissions={"daily-bar": retention_allowed},
            export_permissions={"daily-bar": export_allowed},
            confirmed_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )

    if not retention_allowed:
        with pytest.raises(CompliancePolicyError):
            service.persist_observation(
                PROVIDER_NAME,
                "daily-bar",
                datetime(2025, 1, 1, tzinfo=UTC),
                {"asset_id": "asset-a"},
            )
    if not export_allowed:
        with pytest.raises(CompliancePolicyError):
            service.export_observation(
                PROVIDER_NAME,
                "daily-bar",
                datetime(2025, 1, 1, tzinfo=UTC),
                ("asset-a",),
            )
    assert repository.history(PROVIDER_NAME) == (profile,)
