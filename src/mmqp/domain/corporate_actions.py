from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from mmqp.domain.errors import DomainError, ProblemV1


@dataclass(frozen=True, slots=True)
class CorporateActionVersion:
    canonical_asset_id: str
    event_id: str
    action_type: str
    announcement_date: date
    ex_date: date
    record_date: date | None
    effective_date: date
    terms: Mapping[str, str]
    provenance_id: str
    version_id: str


class CorporateActionValidationError(DomainError):
    def __init__(self, fields: list[str] | None = None):
        super().__init__(
            ProblemV1(
                kind="corporate-action/record-invalid",
                title="Invalid corporate action version",
                status=400,
                detail=(None if fields is None else f"corporate action invalid: {', '.join(fields)}"),
            )
        )
        self.fields = fields
