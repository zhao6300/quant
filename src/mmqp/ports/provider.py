from typing import Protocol

from mmqp.domain.providers import (
    ProviderAdapterRegistration,
    ProviderAdapterStatusV1,
)


class ProviderAdapterRegistry(Protocol):
    def get(self, adapter_id: str) -> ProviderAdapterStatusV1 | None: ...

    def register(self, registration: ProviderAdapterRegistration) -> ProviderAdapterStatusV1: ...

    def update(self, status: ProviderAdapterStatusV1) -> ProviderAdapterStatusV1: ...


class InMemoryProviderAdapterRegistry:
    def __init__(self) -> None:
        self._statuses: dict[str, ProviderAdapterStatusV1] = {}

    def get(self, adapter_id: str) -> ProviderAdapterStatusV1 | None:
        return self._statuses.get(adapter_id)

    def register(self, registration: ProviderAdapterRegistration) -> ProviderAdapterStatusV1:
        status = ProviderAdapterStatusV1(
            adapter_id=registration.adapter_id,
            provider_name=registration.provider_name,
            capabilities=registration.capabilities,
            enabled=False,
        )
        self._statuses[registration.adapter_id] = status
        return status

    def update(self, status: ProviderAdapterStatusV1) -> ProviderAdapterStatusV1:
        self._statuses[status.adapter_id] = status
        return status
