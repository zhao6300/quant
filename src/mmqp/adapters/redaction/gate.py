from collections.abc import Sequence

from mmqp.application.security import SecretRedactionGate
from mmqp.domain.security import SecureCredential


def build_gate(credentials: Sequence[SecureCredential]) -> SecretRedactionGate:
    return SecretRedactionGate(credentials)
