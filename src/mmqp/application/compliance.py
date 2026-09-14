from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

from mmqp.domain.compliance import (
    CompliancePolicyError,
    ComplianceProfileVersionV1,
    ProviderComplianceBindingV1,
)


@dataclass(frozen=True, slots=True)
class ComplianceProfileCommandV1:
    """Data class used when creating/updating a provider compliance profile version."""

    provider_name: str
    account_type: str
    data_categories: tuple[str, ...]
    permitted_purposes: tuple[str, ...]
    retention_permissions: dict[str, bool]
    export_permissions: dict[str, bool]
    confirmed_at: datetime
    predecessor_id: str | None = None


@dataclass(frozen=True, slots=True)
class PersistedProviderObservationV1:
    """
    Observation for a provider request, bound to exactly one profile version.
    """

    provider_name: str
    data_category: str
    observation: Any
    provenance_id: str
    profile_version_id: str


class ComplianceRepository(Protocol):
    def get_current(self, provider_name: str) -> ComplianceProfileVersionV1 | None: ...

    def save_profile(self, profile: ComplianceProfileVersionV1) -> None: ...


class ComplianceService:
    """Controls which profile and provider/observation pair is persisted."""

    def __init__(self, repository: ComplianceRepository) -> None:
        self._repository = repository

    def configure_profile(
        self,
        command: ComplianceProfileCommandV1,
    ) -> ComplianceProfileVersionV1:
        current = self._repository.get_current(command.provider_name)
        predecessor_id = (
            command.predecessor_id
            if command.predecessor_id is not None
            else current.version_id
            if current is not None
            else None
        )
        version_id = uuid4().hex
        profile = _validate_profile(command, version_id, predecessor_id)
        self._repository.save_profile(profile)
        return profile

    def bind(
        self,
        provider_name: str,
        request_category: str,
        request_time: datetime,
    ) -> ProviderComplianceBindingV1:
        profile = self._repository.get_current(provider_name)
        if profile is None:
            raise CompliancePolicyError(
                "compliance/profile-missing",
                f"No valid compliance profile for provider {provider_name!r}",
                provider_name=provider_name,
                data_category=request_category,
            )
        if not _request_time_within_profile(profile, request_time):
            raise CompliancePolicyError(
                "compliance/profile-inactive",
                f"Compliance profile for provider {provider_name!r} is not active",
                provider_name=provider_name,
                data_category=request_category,
            )
        if request_category not in profile.data_categories:
            raise CompliancePolicyError(
                "compliance/category-unsupported",
                f"Data category {request_category!r} is not covered for provider {provider_name!r}",
                provider_name=provider_name,
                data_category=request_category,
            )
        return ProviderComplianceBindingV1(
            profile=profile,
            provider_name=provider_name,
            request_category=request_category,
            request_time=request_time,
            retention_allowed=bool(profile.retention_permissions[request_category]),
            export_allowed=bool(profile.export_permissions[request_category]),
        )

    def persist_observation(
        self,
        provider_name: str,
        data_category: str,
        request_time: datetime,
        observation: Any,
    ) -> PersistedProviderObservationV1:
        binding = self.bind(provider_name, data_category, request_time)
        if not binding.retention_allowed:
            raise CompliancePolicyError(
                "compliance/retention-prohibited",
                "Retention of the observation is prohibited",
                provider_name=provider_name,
                data_category=data_category,
            )
        return PersistedProviderObservationV1(
            provider_name=provider_name,
            data_category=data_category,
            observation=observation,
            provenance_id=uuid4().hex,
            profile_version_id=binding.profile.version_id,
        )

    def export_observation(
        self,
        provider_name: str,
        data_category: str,
        request_time: datetime,
        allowed_values: Iterable[str],
    ) -> tuple[str, ComplianceProfileVersionV1]:
        binding = self.bind(provider_name, data_category, request_time)
        if not binding.export_allowed:
            raise CompliancePolicyError(
                "compliance/export-prohibited",
                "Export of the observation is prohibited",
                provider_name=provider_name,
                data_category=data_category,
            )
        return ",".join(allowed_values), binding.profile


def _validate_profile(
    command: ComplianceProfileCommandV1,
    version_id: str,
    predecessor_id: str | None,
) -> ComplianceProfileVersionV1:
    fields: list[str] = []
    if command.provider_name == "":
        fields.append("provider_name")
    if command.account_type == "":
        fields.append("account_type")
    if not command.permitted_purposes:
        fields.append("permitted_purposes")
    if not command.data_categories:
        fields.append("data_categories")
    if set(command.data_categories) != set(command.retention_permissions):
        fields.append("retention_permissions")
    if set(command.data_categories) != set(command.export_permissions):
        fields.append("export_permissions")
    if command.confirmed_at.tzinfo is None:
        fields.append("confirmed_at")
    if fields:
        raise CompliancePolicyError(
            "compliance/profile-invalid",
            f"Invalid compliance profile fields: {', '.join(fields)}",
            provider_name=command.provider_name,
            data_category=",".join(command.data_categories),
        )
    return ComplianceProfileVersionV1(
        provider_name=command.provider_name,
        account_type=command.account_type,
        data_categories=tuple(command.data_categories),
        permitted_purposes=tuple(command.permitted_purposes),
        retention_permissions=command.retention_permissions,
        export_permissions=command.export_permissions,
        confirmed_at=command.confirmed_at,
        version_id=version_id,
        predecessor_id=predecessor_id,
    )


def _request_time_within_profile(
    profile: ComplianceProfileVersionV1,
    request_time: datetime,
) -> bool:
    return request_time >= profile.confirmed_at
