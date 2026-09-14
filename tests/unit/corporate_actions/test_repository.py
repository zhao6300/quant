from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from mmqp.adapters.sqlite.corporate_actions import SqliteCorporateActionRepository
from mmqp.application.corporate_actions import CorporateActionService
from mmqp.domain.corporate_actions import CorporateActionValidationError, CorporateActionVersion
from mmqp.domain.errors import DomainError


def _action(version_id: str = "ca-1") -> CorporateActionVersion:
    return CorporateActionVersion(
        canonical_asset_id="ASSET_1",
        event_id="ca-event-1",
        action_type="CASH_DIVIDEND",
        announcement_date=date(2024, 1, 2),
        ex_date=date(2024, 1, 3),
        record_date=date(2024, 1, 5),
        effective_date=date(2024, 1, 6),
        terms={"distribution": "1.00", "currency": "USD"},
        provenance_id="prov-holder",
        version_id=version_id,
    )


def test_creates_lists_and_enforces_version_idempotency(tmp_path: Path) -> None:
    repository = SqliteCorporateActionRepository(tmp_path / "corporate.sql")
    service = CorporateActionService(repository)
    action = service.create(_action())
    assert repository.list() == [action]
    with pytest.raises(DomainError):
        service.create(_action())


def test_validation_rejects_required_fields_and_ordering(tmp_path: Path) -> None:
    repository = SqliteCorporateActionRepository(tmp_path / "corporate.sql")
    service = CorporateActionService(repository)
    invalid = replace(
        _action(),
        canonical_asset_id="",
        record_date=None,
        terms={},
    )
    with pytest.raises(CorporateActionValidationError) as error:
        service.create(invalid)
    assert set(error.value.fields) >= {"canonical_asset_id"}
