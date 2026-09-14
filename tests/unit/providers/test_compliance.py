from datetime import UTC, datetime
from pathlib import Path

import pytest

from mmqp.adapters.sqlite.compliance import SqliteComplianceRepository
from mmqp.application.compliance import (
    ComplianceProfileCommandV1,
    ComplianceService,
)
from mmqp.domain.compliance import CompliancePolicyError, ComplianceProfileVersionV1

REQUEST_AT = datetime(2025, 1, 1, tzinfo=UTC)


def _profile_command(
    retention_allowed: bool = True,
    export_allowed: bool = True,
    provider_name: str = "provider-a",
) -> ComplianceProfileCommandV1:
    return ComplianceProfileCommandV1(
        provider_name=provider_name,
        account_type="research",
        data_categories=("daily-bar",),
        permitted_purposes=("academic-research",),
        retention_permissions={"daily-bar": retention_allowed},
        export_permissions={"daily-bar": export_allowed},
        confirmed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )


class _CurrentProfileRepositoryStub:
    def __init__(self, profile: ComplianceProfileVersionV1 | None):
        self._profile = profile

    def get_current(self, provider_name: str) -> ComplianceProfileVersionV1 | None:
        del provider_name
        return self._profile

    def save_profile(self, profile: ComplianceProfileVersionV1) -> None:
        raise AssertionError("compliance profiles should not change at request time")


def test_profile_must_precede_binding() -> None:
    repository = _CurrentProfileRepositoryStub(None)
    service = ComplianceService(repository)

    with pytest.raises(CompliancePolicyError) as error:
        service.bind("provider-a", "daily-bar", REQUEST_AT)

    assert error.value.problem.kind == "compliance/profile-missing"


def test_prohibited_retention_does_not_persist() -> None:
    repository = _CurrentProfileRepositoryStub(
        ComplianceProfileVersionV1(
            provider_name="provider-a",
            account_type="research",
            data_categories=("daily-bar",),
            permitted_purposes=("academic-research",),
            retention_permissions={"daily-bar": False},
            export_permissions={"daily-bar": True},
            confirmed_at=datetime(2024, 1, 1, tzinfo=UTC),
            version_id="version-a",
        ),
    )
    service = ComplianceService(repository)

    with pytest.raises(CompliancePolicyError) as error:
        service.persist_observation("provider-a", "daily-bar", REQUEST_AT, {"close": 1.0})

    assert error.value.problem.kind == "compliance/retention-prohibited"


def test_prohibited_export_has_no_bytes_and_records_profile() -> None:
    repository = _CurrentProfileRepositoryStub(
        ComplianceProfileVersionV1(
            provider_name="provider-a",
            account_type="research",
            data_categories=("daily-bar",),
            permitted_purposes=("academic-research",),
            retention_permissions={"daily-bar": True},
            export_permissions={"daily-bar": False},
            confirmed_at=datetime(2024, 1, 1, tzinfo=UTC),
            version_id="version-a",
        ),
    )
    service = ComplianceService(repository)

    with pytest.raises(CompliancePolicyError) as error:
        service.export_observation("provider-a", "daily-bar", REQUEST_AT, ("close=1.0",))

    assert error.value.problem.kind == "compliance/export-prohibited"
    assert error.value.data_category == "daily-bar"


def test_allowed_observation_binds_exactly_one_profile_and_export() -> None:
    repository = _CurrentProfileRepositoryStub(
        ComplianceProfileVersionV1(
            provider_name="provider-a",
            account_type="research",
            data_categories=("daily-bar",),
            permitted_purposes=("academic-research",),
            retention_permissions={"daily-bar": True},
            export_permissions={"daily-bar": True},
            confirmed_at=datetime(2024, 1, 1, tzinfo=UTC),
            version_id="version-a",
        ),
    )
    service = ComplianceService(repository)

    persisted = service.persist_observation("provider-a", "daily-bar", REQUEST_AT, {"close": 1.0})
    profile = service.export_observation("provider-a", "daily-bar", REQUEST_AT, ("close=1.0",))[1]

    assert persisted.profile_version_id == "version-a"
    assert profile.version_id == "version-a"


def test_sqlite_profile_versions_are_immutable_and_predecessors_are_preserved(
    tmp_path: Path,
) -> None:
    repository = SqliteComplianceRepository(tmp_path / "compliance.sqlite")
    service = ComplianceService(repository)
    first = service.configure_profile(_profile_command(retention_allowed=True, export_allowed=False))
    second = service.configure_profile(_profile_command(retention_allowed=False, export_allowed=True))

    history = repository.history("provider-a")
    assert first.version_id != second.version_id
    assert second.predecessor_id == first.version_id
    assert [item.version_id for item in history] == [first.version_id, second.version_id]
    assert repository.get_current("provider-a") == second
