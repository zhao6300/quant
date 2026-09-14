"""In-memory keychain adapter used only for tests and local tools."""

from mmqp.domain.security import SecureCredential


class MemoryKeychain:
    def __init__(self) -> None:
        self._state: dict[str, SecureCredential] = {}

    def set(self, credential: SecureCredential) -> None:
        self._state[credential.summary.credential_id] = credential

    def list(self) -> tuple[SecureCredential, ...]:
        return tuple(self._state.values())

    def delete(self, credential_id: str) -> None:
        try:
            del self._state[credential_id]
        except KeyError as error:
            raise RuntimeError("credential is not stored") from error
