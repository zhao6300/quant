import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mmqp.adapters.sqlite.workspace_repository import SqliteWorkspaceRepository
from mmqp.application.uow import WorkspaceUnitOfWork
from mmqp.domain.workspace import WorkspaceRecord


def _workspace(root: Path, _repository: SqliteWorkspaceRepository) -> WorkspaceRecord:
    record = WorkspaceRecord(
        id=uuid.uuid4().hex,
        path=str(root),
        display_name="UOW",
        bound_uid=os.geteuid(),
        created_at=datetime.now(UTC),
    )
    _repository.create(record)
    return record


def _object_count(database: Path) -> int:
    with sqlite3.connect(database) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM workspace_objects").fetchone()[0])


def test_workspace_uow_commits_staged_object_idempotently(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace", SqliteWorkspaceRepository(tmp_path / "workspaces.sqlite3"))
    unit = WorkspaceUnitOfWork(workspace)
    unit.begin("fixture")
    staged_hash = unit.stage(
        kind="fixture",
        schema_id="fixture-binary",
        schema_version=1,
        record_count=1,
        content=b"payload",
    )
    result = unit.commit()
    object_path = tmp_path / "workspace" / "objects" / "sha256" / staged_hash[:2] / f"{staged_hash}.bin"
    assert result.object_ids == (staged_hash,)
    assert object_path.read_bytes() == b"payload"
    assert _object_count(tmp_path / "workspace" / "control.sqlite3") == 1

    duplicate_unit = WorkspaceUnitOfWork(workspace)
    duplicate_unit.begin("fixture")
    duplicate_unit.stage(
        kind="fixture",
        schema_id="fixture-binary",
        schema_version=1,
        record_count=1,
        content=b"payload",
    )
    duplicate_result = duplicate_unit.commit()
    assert duplicate_result.object_ids == (staged_hash,)
    assert _object_count(tmp_path / "workspace" / "control.sqlite3") == 1


def test_workspace_uow_rolls_back_staged_object_without_publication(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace", SqliteWorkspaceRepository(tmp_path / "workspaces.sqlite3"))
    unit = WorkspaceUnitOfWork(workspace)

    unit.begin("fixture")
    unit.stage(
        kind="fixture",
        schema_id="fixture-binary",
        schema_version=1,
        record_count=1,
        content=b"payload",
    )
    unit.rollback()
    assert _object_count(tmp_path / "workspace" / "control.sqlite3") == 0
    assert not any((tmp_path / "workspace" / "objects" / "sha256").glob("*/*"))


def test_workspace_uow_refuses_conflicting_preexisting_object(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace", SqliteWorkspaceRepository(tmp_path / "workspaces.sqlite3"))
    hashlib_needed = __import__("hashlib").sha256(b"payload").hexdigest()
    object_path = tmp_path / "workspace" / "objects" / "sha256" / hashlib_needed[:2] / f"{hashlib_needed}.bin"
    object_path.parent.mkdir(parents=True, exist_ok=True)
    object_path.write_bytes(b"\x00noise")

    unit = WorkspaceUnitOfWork(workspace)
    unit.begin("fixture")
    unit.stage(
        kind="fixture",
        schema_id="fixture-binary",
        schema_version=1,
        record_count=1,
        content=b"payload",
    )
    with pytest.raises(FileExistsError, match="object hash conflict"):
        unit.commit()

    assert _object_count(tmp_path / "workspace" / "control.sqlite3") == 0
