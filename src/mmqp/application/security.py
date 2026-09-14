import os
from collections.abc import Mapping, Sequence
from typing import Any, cast
from urllib.parse import unquote, urlsplit

from mmqp.domain.security import (
    CredentialDeletionChoiceV1,
    CredentialDeletionFailureV1,
    CredentialDeletionResultV1,
    CredentialSummary,
    CredentialUnavailableError,
    NonProviderDestination,
    ProviderEndpointV1,
    SecureCredential,
    SecurityError,
)


def _redact(value: object, materials: tuple[str, ...]) -> object:
    if isinstance(value, str):
        for material in materials:
            value = value.replace(material, "[REDACTED]")
        return value
    if isinstance(value, Mapping):
        return {key: _redact(item, materials) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, materials) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item, materials) for item in value)
    if isinstance(value, bytes):
        text = value.decode("utf-8")
        redacted = _redact(text, materials)
        return redacted.encode("utf-8") if isinstance(redacted, str) else redacted
    return value


class SecretRedactionGate:
    def __init__(self, credentials: Sequence[SecureCredential]):
        self._materials = tuple(
            sorted(
                (
                    material
                    for credential in credentials
                    for material in (credential.value, *credential.configured_representations)
                    if material
                ),
                key=len,
                reverse=True,
            ),
        )

    def redact(self, value: object) -> object:
        try:
            return _redact(value, self._materials)
        except Exception:
            raise SecurityError("security/redaction-uncertain", "Credential redaction failed") from None


class NetworkScopeService:
    def __init__(self, endpoint: ProviderEndpointV1):
        self._origin = _validate_origin(endpoint.origin)
        self._allowed_path_scope = _validate_path(endpoint.allowed_path_scope)

    @property
    def origin(self) -> str:
        return self._origin

    def allows(self, target: str, redirect: str | None = None) -> bool:
        return self._allows_target(target) and (redirect is None or self._allows_target(redirect))

    def _allows_target(self, target: str) -> bool:
        try:
            parts = urlsplit(target)
            if parts.scheme != "https" or parts.username is not None or parts.query or parts.fragment:
                return False
            host = parts.hostname
            port = parts.port
            if not host or port is None:
                return False
            if f"https://{host.lower()}:{port}" != self._origin:
                return False
            return _normalize_path(parts.path).startswith(self._allowed_path_scope)
        except (SecurityError, ValueError):
            return False


def _validate_origin(origin: str) -> str:
    try:
        parts = urlsplit(origin)
        if parts.scheme != "https" or parts.username is not None or parts.path not in {"", "/"}:
            raise SecurityError("security/endpoint-invalid", "Provider endpoint must be an HTTPS origin")
        host = parts.hostname
        port = parts.port
        if not host or port is None:
            raise SecurityError("security/endpoint-invalid", "Provider endpoint host and port are required")
        return f"https://{host.lower()}:{port}"
    except ValueError as error:
        raise SecurityError("security/endpoint-invalid", "Provider endpoint origin is invalid") from error


def _validate_path(path: str) -> str:
    try:
        if not path.startswith("/") or path == "/":
            raise SecurityError("security/endpoint-invalid", "Allowed path scope must be rooted")
        return _normalize_path(path)
    except SecurityError:
        raise
    except Exception as error:
        raise SecurityError("security/endpoint-invalid", "Allowed path scope must be rooted") from error


def _normalize_path(path: str) -> str:
    if path == "/":
        return "/"
    if path.startswith("//") or any(character in path for character in ("\x00", "\r", "\n")):
        raise SecurityError("security/endpoint-invalid", "Path scope must be rooted")
    decoded_segments: list[str] = []
    for raw_segment in path.split("/"):
        segment = unquote(raw_segment)
        if segment in {"", "."}:
            continue
        if segment == "..":
            try:
                decoded_segments.pop()
            except IndexError as error:
                raise SecurityError("security/endpoint-invalid", "Path scope must be rooted") from error
            continue
        decoded_segments.append(segment)
    return "/" + "/".join(decoded_segments) if decoded_segments else "/"


class NonProviderEgressPolicy:
    def __init__(self, redaction_gate: SecretRedactionGate):
        self._redaction_gate = redaction_gate

    def prepare(
        self,
        destination: NonProviderDestination,
        named: str,
        category: str,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        if destination.name != named or destination.category != category:
            raise SecurityError("security/egress-not-consented", "Outbound destination is not consented")
        return cast(Mapping[str, object], self._redaction_gate.redact(payload))


class CredentialManager:
    def __init__(self, store: Any):
        self._store = store
        self._endpoint: ProviderEndpointV1 | None = None

    @property
    def endpoint(self) -> ProviderEndpointV1 | None:
        return self._endpoint

    def configure_endpoint(
        self,
        previous: ProviderEndpointV1,
        proposed: ProviderEndpointV1,
    ) -> ProviderEndpointV1:
        try:
            NetworkScopeService(proposed)
        except SecurityError:
            return previous
        self._endpoint = proposed
        return proposed

    def set(self, credential: SecureCredential, requester_uid: int) -> CredentialSummary:
        if credential.summary.owner_uid != requester_uid or requester_uid != os.getuid():
            raise CredentialUnavailableError(credential.summary.provider_name)
        if not credential.value:
            raise SecurityError("security/credential-empty", "Credential value must not be empty")
        credential_store = cast(Any, self._store)
        credential_store.set(credential)
        return credential.summary

    def credential_choices(self) -> tuple[CredentialSummary, ...]:
        return tuple(item.summary for item in self._store.list())

    def retrieve(self, provider_name: str, requester_uid: int) -> str:
        selection = [
            item
            for item in self._store.list()
            if item.summary.provider_name == provider_name
            and item.summary.owner_uid == requester_uid
            and requester_uid == os.getuid()
        ]
        if selection:
            return str(selection[0].value)
        raise CredentialUnavailableError(provider_name)

    def deletion_options(self) -> tuple[CredentialSummary, ...]:
        return tuple(item.summary for item in self._store.list())

    def delete_selected(self, choices: Sequence[CredentialDeletionChoiceV1]) -> CredentialDeletionResultV1:
        selected = tuple(choice.credential_id for choice in choices if choice.delete)
        current = tuple(self._store.list())
        known_ids = {item.summary.credential_id for item in current}
        if len(set(selected)) != len(selected) or any(item not in known_ids for item in selected):
            raise SecurityError(
                "security/credential-selection-invalid", "Credential deletion selection is invalid"
            )
        selected_set = set(selected)
        complement = tuple(
            item.summary.credential_id for item in current if item.summary.credential_id not in selected_set
        )
        originals = {
            item.summary.credential_id: item for item in current if item.summary.credential_id in selected_set
        }
        credential_store = cast(Any, self._store)
        try:
            for credential_id in selected:
                credential_store.delete(credential_id)
        except Exception:
            for credential_id in selected:
                if credential_id in originals:
                    credential_store.set(originals[credential_id])
            return CredentialDeletionResultV1(
                deleted=(),
                preserved=selected + complement,
                failures=tuple(CredentialDeletionFailureV1(credential_id) for credential_id in selected),
            )
        return CredentialDeletionResultV1(deleted=selected, preserved=complement, failures=())
