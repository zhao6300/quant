from collections.abc import Mapping
from datetime import UTC, datetime
from os import getuid
from typing import Any

from mmqp.adapters.keychain.macos import MemoryKeychain
from mmqp.application.security import CredentialManager
from mmqp.domain.providers import (
    ProviderAdapterStatusV1,
    ProviderCategorizedError,
    ProviderNormalizedResponseV1,
    ProviderResponseEnvelopeV1,
)
from mmqp.domain.security import SecureCredential
from tests.fixtures.providers.local_https import LocalHTTPSProvider

PROVIDER_NAME = "contract-provider"


def _blocked() -> ProviderCategorizedError:
    return ProviderCategorizedError(
        category="policy_blocked",
        provider_name=PROVIDER_NAME,
        request_category="daily-bar",
        status=503,
    )


class LocalHTTPSAdapter:
    """Adapt the offline local TLS provider fixture to the V1 provider boundary."""

    def __init__(self, provider: LocalHTTPSProvider) -> None:
        self.provider = provider
        self.status: ProviderAdapterStatusV1 | None = None
        self.enabled = False
        self.credential_shown = False
        self.credential_manager = CredentialManager(MemoryKeychain())
        self.sent: list[str] = []

    def configure_capabilities(self, status: ProviderAdapterStatusV1) -> None:
        self.status = status

    def enable_after_display(self) -> None:
        self.credential_shown = True
        self.enabled = True

    def set_credential(self, credential: SecureCredential, user_uid: int) -> None:
        self.credential_manager.set(credential, user_uid)

    def request(
        self,
        path: str,
        *,
        request_parameters: Mapping[str, Any] | None = None,
    ) -> ProviderResponseEnvelopeV1:
        parameters = {"request": "offline"} if request_parameters is None else dict(request_parameters)
        if self.status is not None and not self.status.enabled:
            raise _blocked()
        if self.status is None or not self.enabled:
            raise _blocked()
        if not self.provider.scope.allows(f"{self.provider.origin}{path}"):
            raise _blocked()
        if not self.credential_shown:
            assert self.credential_manager.retrieve(PROVIDER_NAME, getuid())
        self.sent.append(path)
        self.provider.request(path, parameters)
        return ProviderResponseEnvelopeV1(
            provider_name=PROVIDER_NAME,
            request_category="daily-bar",
            request_parameters=parameters,
            retrieval_time=datetime.now(UTC),
            normalized=ProviderNormalizedResponseV1({"ok": True}),
        )


OfflineHTTPSAdapter = LocalHTTPSAdapter
