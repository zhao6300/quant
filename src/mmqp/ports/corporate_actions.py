from builtins import list as list_type
from typing import Protocol

from mmqp.domain.corporate_actions import CorporateActionVersion


class CorporateActionRepository(Protocol):
    """Persistence port for immutable corporate action versions."""

    def create(self, action: CorporateActionVersion) -> CorporateActionVersion: ...

    def list(self) -> list_type[CorporateActionVersion]: ...

    def close(self) -> None: ...
