from builtins import list as list_type
from typing import Protocol

from mmqp.domain.universes import UniverseMembership


class UniverseMembershipRepository(Protocol):
    def create(self, membership: UniverseMembership) -> UniverseMembership: ...
    def list(self) -> list_type[UniverseMembership]: ...
    def find(self, membership_id: str) -> UniverseMembership | None: ...
