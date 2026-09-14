from mmqp.application.security import NetworkScopeService
from mmqp.domain.security import ProviderEndpointV1


def provider_scope(origin: str, allowed_path_scope: str) -> NetworkScopeService:
    return NetworkScopeService(ProviderEndpointV1(origin, allowed_path_scope))
