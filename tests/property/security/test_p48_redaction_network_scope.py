from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.application.security import NetworkScopeService, NonProviderEgressPolicy, SecretRedactionGate
from mmqp.domain.security import (
    CredentialSummary,
    NonProviderDestination,
    ProviderEndpointV1,
    SecureCredential,
)


@given(
    origin=st.sampled_from(("https://api.example.com:443", "https://api.example.com:443")),
    path_scope=st.sampled_from(("/secure", "/static")),
)
@settings(max_examples=8, deadline=None)
def test_scope_and_redaction_fail_closed(origin, path_scope):
    credential = SecureCredential(CredentialSummary("api", "p", 0), ("abc#",), "abc")
    gate = SecretRedactionGate([credential])
    scope = NetworkScopeService(ProviderEndpointV1(origin, path_scope))
    assert scope.allows(f"{origin}{path_scope}/same") is True
    assert scope.allows(f"{origin}{path_scope}/../other") is False
    assert gate.redact("abc abc#") == "[REDACTED] [REDACTED]"
    egress = NonProviderEgressPolicy(gate)
    assert egress.prepare(NonProviderDestination("local", "logs"), "local", "logs", {"token": "abc"}) == {
        "token": "[REDACTED]"
    }
