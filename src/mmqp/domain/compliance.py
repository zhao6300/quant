from dataclasses import dataclass
from datetime import datetime

from mmqp.domain.errors import DomainError, ProblemV1


@dataclass(frozen=True, slots=True)
class ComplianceProfileVersionV1:
    """Immutable compliance profile version for one provider."""

    provider_name: str
    account_type: str
    data_categories: tuple[str, ...]
    permitted_purposes: tuple[str, ...]
    retention_permissions: dict[str, bool]
    export_permissions: dict[str, bool]
    confirmed_at: datetime
    version_id: str
    predecessor_id: str | None = None

    def __post_init__(self) -> None:
        if self.provider_name == "":
            raise ValueError("provider_name is required")
        if self.version_id == "":
            raise ValueError("version_id is required")
        if self.confirmed_at.tzinfo is None:
            raise ValueError("confirmed_at must include a UTC offset")


@dataclass(frozen=True, slots=True)
class ProviderComplianceBindingV1:
    profile: ComplianceProfileVersionV1
    provider_name: str
    request_category: str
    request_time: datetime
    retention_allowed: bool
    export_allowed: bool


class CompliancePolicyError(DomainError):
    """Raised when compliance/sentinel policy violations are found."""

    def __init__(
        self,
        problem_kind: str = "compliance/restricted",
        message: str = "Compliance policy violation",
        *,
        provider_name: str = "",
        data_category: str,
    ) -> None:
        extra = (
            {
                "provider": [provider_name],
                "data_category": [data_category],
            }
            if provider_name
            else {"data_category": [data_category]}
        )
        super().__init__(
            ProblemV1(
                kind=problem_kind,
                title="Compliance policy violation",
                status=403,
                detail=message,
                fields=extra,
            )
        )
        self.provider_name = provider_name
        self.data_category = data_category
