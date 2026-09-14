from __future__ import annotations

from mmqp.domain.corporate_actions import CorporateActionValidationError, CorporateActionVersion
from mmqp.ports.corporate_actions import CorporateActionRepository


class CorporateActionService:
    def __init__(self, repository: CorporateActionRepository):
        self._repository = repository

    def create(self, action: CorporateActionVersion) -> CorporateActionVersion:
        self._validate(action)
        return self._repository.create(action)

    def list(self) -> list[CorporateActionVersion]:
        return self._repository.list()

    def _validate(self, action: CorporateActionVersion) -> None:
        _validate(action)


def _validate(action: CorporateActionVersion) -> None:
    fields: list[str] = []
    if not action.canonical_asset_id.strip():
        fields.append("canonical_asset_id")
    if not action.event_id.strip():
        fields.append("event_id")
    if not action.action_type.strip():
        fields.append("action_type")
    if not action.provenance_id.strip():
        fields.append("provenance_id")
    if not action.version_id.strip():
        fields.append("version_id")
    if action.ex_date < action.announcement_date:
        fields.append("ex_date.before_announcement")
    if action.effective_date < action.ex_date:
        fields.append("effective_date.before_ex_date")
    if action.record_date is not None and action.record_date > action.effective_date:
        fields.append("record_date.after_effective_date")
    if not action.terms:
        fields.append("terms.missing")
    if fields:
        raise CorporateActionValidationError(fields)
