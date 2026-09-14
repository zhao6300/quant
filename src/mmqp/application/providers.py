from dataclasses import replace

from mmqp.domain.providers import (
    AdapterCapabilitiesV1,
    ProviderAdapterRegistration,
    ProviderAdapterStatusV1,
    ProviderCapabilityError,
)
from mmqp.ports.provider import InMemoryProviderAdapterRegistry


class ProviderAdapterService:
    contract_version = "1.0"
    contract_states = frozenset({"supported", "unsupported", "unknown"})

    def __init__(
        self,
        registry: InMemoryProviderAdapterRegistry | None = None,
    ) -> None:
        self._registry = registry if registry is not None else InMemoryProviderAdapterRegistry()
        self._seen: set[str] = set()

    def register(
        self,
        registration: ProviderAdapterRegistration,
    ) -> ProviderAdapterStatusV1:
        self._validate_registration(registration)
        status = self._registry.register(registration)
        if registration.capabilities.contract_version != self.contract_version:
            return replace(
                status,
                incompatible_reason=(
                    f"unsupported-contract-version:{registration.capabilities.contract_version}"
                ),
            )
        if status.incompatible_reason is not None:
            return status
        return status

    def display(self, adapter_id: str) -> ProviderAdapterStatusV1 | None:
        status = self._registry.get(adapter_id)
        if status is not None:
            self._seen.add(adapter_id)
        return status

    def status(
        self,
        adapter_id: str,
    ) -> ProviderAdapterStatusV1:
        return self._get(adapter_id)

    def enable(self, adapter_id: str) -> ProviderAdapterStatusV1:
        status = self._get(adapter_id)
        if status.incompatible_reason is not None:
            raise ProviderCapabilityError(
                fields=[status.capabilities.contract_version],
                status=409,
            )
        if adapter_id not in self._seen:
            raise ProviderCapabilityError(
                fields=["capabilities"],
                status=409,
            )
        return self._registry.update(replace(status, enabled=True))

    def _get(self, adapter_id: str) -> ProviderAdapterStatusV1:
        status = self._registry.get(adapter_id)
        if status is None:
            raise ProviderCapabilityError(
                fields=["adapter_id"],
                status=404,
            )
        return status

    def _validate_registration(self, registration: ProviderAdapterRegistration) -> None:
        if registration.adapter_id == "":
            raise ProviderCapabilityError(fields=["adapter_id"])
        if not registration.provider_name.strip():
            raise ProviderCapabilityError(fields=["provider_name"])
        self._normalize(registration.capabilities)

    def _normalize(self, capabilities: AdapterCapabilitiesV1) -> None:
        if capabilities.contract_version != self.contract_version:
            return
        fields: list[str] = []
        if capabilities.normalized_response not in self.contract_states:
            fields.append("normalized_response")
        if capabilities.provenance not in self.contract_states:
            fields.append("provenance")
        if capabilities.categorized_errors not in self.contract_states:
            fields.append("categorized_errors")
        if capabilities.request_limits is not None and not (
            1 <= capabilities.request_limits.max_requests_per_period <= 1_000_000
            and 1 <= capabilities.request_limits.measurement_period_seconds <= 86_400
        ):
            fields.append("request_limits")
        if fields:
            raise ProviderCapabilityError(fields=fields)
