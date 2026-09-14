from mmqp.application.security import SecretRedactionGate
from mmqp.domain.security import CredentialSummary, SecureCredential


def secret(value="abc"):
    return SecureCredential(CredentialSummary(credential_id="api", provider_name="p", owner_uid=0), (), value)


def test_redaction_removes_exact_and_configured_material():
    credential = SecureCredential(
        CredentialSummary(credential_id="api", provider_name="p", owner_uid=0),
        ("abc#",),
        "abc",
    )
    gate = SecretRedactionGate([credential])
    assert gate.redact("abc abc#def") == "[REDACTED] [REDACTED]def"
