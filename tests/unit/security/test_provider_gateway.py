import pytest

from mmqp.application.security import CredentialManager
from mmqp.domain.security import CredentialUnavailableError
from tests.unit.security.test_credentials import MemoryKeychain


def test_unavailable_credential_prevents_provider_sending():
    sent = 0
    manager = CredentialManager(MemoryKeychain())
    with pytest.raises(CredentialUnavailableError):
        manager.retrieve("test", 0)
    assert sent == 0
