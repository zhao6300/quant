import pytest

from mmqp.application.security import CredentialManager
from mmqp.domain.security import CredentialSummary, CredentialUnavailableError, SecureCredential


class MemoryKeychain:
    def __init__(self):
        self.items = {}
        self.failing_on_delete = None

    def set(self, credential):
        self.items[credential.summary.credential_id] = credential

    def list(self):
        return tuple(self.items.values())

    def delete(self, credential_id):
        if credential_id == self.failing_on_delete:
            raise RuntimeError("deletion failed")
        del self.items[credential_id]


def other_credentials(name: str, value: str):
    return SecureCredential(CredentialSummary(name, name, 0), (), value)


def credential(name, key, value="secret"):
    return SecureCredential(CredentialSummary(key, name, 0), (), value)


def test_same_uid_can_retrieve_and_other_uid_is_unavailable():
    manager = CredentialManager(MemoryKeychain())
    manager.set(credential("test", "test"), 0)
    assert manager.retrieve("test", 0) == "secret"
    with pytest.raises(CredentialUnavailableError):
        manager.retrieve("test", 1)
