from mmqp.application.security import CredentialManager
from mmqp.domain.security import ProviderEndpointV1
from tests.unit.security.test_credentials import MemoryKeychain


def test_invalid_endpoint_preserves_previous_endpoint():
    manager = CredentialManager(MemoryKeychain())
    previous = ProviderEndpointV1("https://api.example.com:443", "/secure")
    proposed = ProviderEndpointV1("http://api.example.com:443", "/secure")
    assert manager.configure_endpoint(previous, proposed) == previous
