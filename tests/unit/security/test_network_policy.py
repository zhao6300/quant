from mmqp.application.security import NetworkScopeService
from mmqp.domain.security import ProviderEndpointV1


def endpoint(origin="https://api.example.com:443", allowed_path_scope="/secure"):
    return ProviderEndpointV1(origin=origin, allowed_path_scope=allowed_path_scope)


def test_network_scope_is_https_and_path_bounded():
    service = NetworkScopeService(endpoint())
    assert service.allows("https://api.example.com:443/secure/x")
    assert not service.allows("http://api.example.com:443/secure/x")
