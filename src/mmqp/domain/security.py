from dataclasses import dataclass

from mmqp.domain.errors import DomainError, ProblemV1


@dataclass(frozen=True, slots=True)
class CredentialSummary:
    credential_id: str
    provider_name: str
    owner_uid: int


@dataclass(frozen=True, slots=True)
class SecureCredential:
    summary: CredentialSummary
    configured_representations: tuple[str, ...]
    value: str


@dataclass(frozen=True, slots=True)
class ProviderEndpointV1:
    origin: str
    allowed_path_scope: str


@dataclass(frozen=True, slots=True)
class ProviderAuthCommandV1:
    provider_name: str
    owner_uid: int


@dataclass(frozen=True, slots=True, kw_only=True)
class CredentialDeletionChoiceV1:
    credential_id: str
    delete: bool


@dataclass(frozen=True, slots=True)
class CredentialDeletionFailureV1:
    credential_id: str


@dataclass(frozen=True, slots=True)
class CredentialDeletionResultV1:
    deleted: tuple[str, ...]
    preserved: tuple[str, ...]
    failures: tuple[CredentialDeletionFailureV1, ...]


class SecurityError(DomainError):
    def __init__(self, kind: str, title: str, *, status: int = 403):
        super().__init__(ProblemV1(kind=kind, title=title, status=status))


class CredentialUnavailableError(SecurityError):
    def __init__(self, provider_name: str):
        super().__init__(
            "security/credential-unavailable",
            f"Credential unavailable for provider {provider_name}",
        )


class NonProviderDestination:
    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category
