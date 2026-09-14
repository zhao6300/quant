from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from mmqp.domain.errors import DomainError, ProblemV1

CapabilityState = Literal["supported", "unsupported", "unknown"]
UNKNOWN: CapabilityState = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderRequestLimitsV1:
    max_requests_per_period: int
    measurement_period_seconds: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AdapterCapabilitiesV1:
    contract_version: Literal["1", "1.0"]
    authentication_references: tuple[str, ...] = (UNKNOWN,)
    markets: tuple[str, ...] = (UNKNOWN,)
    asset_types: tuple[str, ...] = (UNKNOWN,)
    categories: tuple[str, ...] = (UNKNOWN,)
    available_from: date | None = None
    available_to: date | None = None
    update_frequencies: tuple[str, ...] = (UNKNOWN,)
    normalized_response: CapabilityState = UNKNOWN
    provenance: CapabilityState = UNKNOWN
    categorized_errors: CapabilityState = UNKNOWN
    request_limits: ProviderRequestLimitsV1 | None = None


@dataclass(frozen=True, slots=True)
class ProviderAdapterRegistration:
    adapter_id: str
    provider_name: str
    capabilities: AdapterCapabilitiesV1


@dataclass(frozen=True, slots=True)
class ProviderAdapterStatusV1:
    adapter_id: str
    provider_name: str
    capabilities: AdapterCapabilitiesV1
    enabled: bool
    incompatible_reason: str | None = None


ProviderErrorCategory = Literal[
    "timeout",
    "throttled",
    "unavailable",
    "authentication",
    "invalid_response",
    "policy_blocked",
]


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    provider_name: str
    request_category: str
    parameters: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ProviderNormalizedResponseV1:
    values: Mapping[str, Any]
    source_version: str | None = None
    provider_correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderResponseEnvelopeV1:
    provider_name: str
    request_category: str
    request_parameters: Mapping[str, Any]
    retrieval_time: datetime
    normalized: ProviderNormalizedResponseV1
    source_version: str | None = None
    provider_correlation_id: str | None = None


class ProviderCapabilityError(DomainError):
    def __init__(self, fields: list[str] | None = None, *, status: int = 400):
        title = "Provider adapter capabilities invalid"
        kind = "provider/capabilities-invalid"
        if status != 400:
            title = "Provider contract incompatible"
            kind = "provider/contract-incompatible"
        super().__init__(
            ProblemV1(
                kind=kind,
                title=title,
                status=status,
                detail=None if fields is None else f"provider capabilities invalid: {', '.join(fields)}",
            )
        )
        self.fields = fields


class ProviderCategorizedError(DomainError):
    def __init__(
        self,
        *,
        category: ProviderErrorCategory,
        provider_name: str,
        request_category: str,
        retry: Literal["never", "safe_immediate", "safe_after"] = "never",
        status: int = 503,
        provider_correlation_id: str | None = None,
    ) -> None:
        fields: dict[str, list[str]] = {
            "provider": [provider_name],
            "request_category": [request_category],
            "retry": [retry],
        }
        if provider_correlation_id is not None:
            fields["provider_correlation_id"] = [provider_correlation_id]
        super().__init__(
            ProblemV1(
                kind=f"provider/{category}",
                title=f"Provider request {category}",
                status=status,
                detail=f"Provider request categorized as {category}.",
                fields=fields,
                retry=retry,
            )
        )
        self.category = category
        self.provider_name = provider_name
        self.request_category = request_category
        self.retry = retry
        self.provider_correlation_id = provider_correlation_id
