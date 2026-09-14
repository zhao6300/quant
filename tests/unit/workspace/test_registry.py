from pathlib import Path

import pytest

from mmqp.adapters.sqlite.workspace_repository import SqliteWorkspaceRepository
from mmqp.application.workspaces import WorkspaceService
from mmqp.domain.workspace import WorkspaceConflictError


@pytest.fixture
def repository(tmp_path: Path) -> SqliteWorkspaceRepository:
    return SqliteWorkspaceRepository(tmp_path / "workspaces.sqlite3")


def test_registry_rejects_workspace_path_conflicts(
    tmp_path: Path, repository: SqliteWorkspaceRepository
) -> None:
    service = WorkspaceService(repository)
    root = tmp_path / "first"
    service.create(str(root), "First")

    invalid_candidates = [str(root), str(root / "child")]
    for candidate in invalid_candidates:
        with pytest.raises(WorkspaceConflictError) as exc_info:
            service.create(candidate, "Conflict")
        assert exc_info.value.problem.status == 409
        assert any(
            conflict.conflict_kind in {"equal-path", "ancestor-or-descendant"}
            for conflict in exc_info.value.conflicts
        )
        assert not (tmp_path / "conflict").exists()
    assert len(repository.list()) == 1


def test_service_open_rejects_uid_mismatch(tmp_path: Path, repository: SqliteWorkspaceRepository) -> None:
    root = tmp_path / "owned"
    root.mkdir()
    import os
    import uuid
    from datetime import UTC, datetime

    from mmqp.domain.workspace import WorkspaceRecord

    record = WorkspaceRecord(
        id=uuid.uuid4().hex,
        path=str(root),
        display_name="owned",
        bound_uid=os.geteuid() + 1,
        created_at=datetime.now(UTC),
    )
    repository.create(record)
    service = WorkspaceService(repository)
    with pytest.raises(WorkspaceConflictError) as exc_info:
        service.open(str(root))
    assert exc_info.value.problem.status == 403
    # The repository still has one bound record.
    assert len(repository.list()) == 1
