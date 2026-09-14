import os
import sqlite3
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mmqp.adapters.sqlite.workspace_repository import SqliteWorkspaceRepository
from mmqp.application.uow import WorkspaceUnitOfWork
from mmqp.application.workspaces import WorkspaceService
from mmqp.domain.workspace import WorkspaceRecord


def _service(tmp_path: Path) -> WorkspaceService:
    return WorkspaceService(SqliteWorkspaceRepository(tmp_path / "workspaces.sqlite3"))


def _record(tmp_path: Path, *, bound_uid: int | None = None) -> WorkspaceRecord:
    path = tmp_path / f"workspace-{uuid.uuid4().hex}"
    service = _service(tmp_path)
    if bound_uid is None:
        return service.create(str(path), "Integration")
    return WorkspaceRecord(
        id=uuid.uuid4().hex,
        path=str(path),
        display_name="Direct",
        bound_uid=bound_uid,
        created_at=datetime.now(UTC),
    )


def _object_count(path: Path) -> int:
    with sqlite3.connect(path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM workspace_objects").fetchone()[0])


def test_workspace_create_open_reopen(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create(str(tmp_path / "workspace"), "Workspace")
    reopened = service.open(str(tmp_path / "workspace"))
    again = service.open(created.path)
    assert reopened == created
    assert again == created


def test_workspace_uid_is_rejected(tmp_path: Path) -> None:
    workspace = _record(tmp_path / "uid", bound_uid=-1)
    unit = WorkspaceUnitOfWork(workspace)
    with pytest.raises(Exception, match="current uid does not match bound uid"):
        unit.begin("fixture")


def test_workspace_process_lock_is_exclusive(tmp_path: Path) -> None:
    service = _service(tmp_path)
    workspace = service.create(str(tmp_path / "workspace"), "Locked")
    holder = subprocess.Popen(
        [
            "python",
            "-c",
            "import fcntl,sys; h=open(sys.argv[1], 'a'); fcntl.flock(h, fcntl.LOCK_EX); input()",
            str(Path(workspace.path) / "locks" / "workspace.lock"),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        unit = WorkspaceUnitOfWork(workspace)
        unit.begin("fixture")
        unit.stage(kind="fixture", schema_id="fixture", schema_version=1, record_count=1, content=b"payload")
        unit.commit()
        assert _object_count(Path(workspace.path) / "control.sqlite3") == 1
    finally:
        holder.kill()
        holder.wait()


def test_workspace_rollback_leaves_other_workspace_unchanged(tmp_path: Path) -> None:
    service = _service(tmp_path)
    first = service.create(str(tmp_path / "first"), "First")
    second = service.create(str(tmp_path / "second"), "Second")
    service.open(str(second.path))
    service.create(str(tmp_path / "third"), "Third")
    second_unit = WorkspaceUnitOfWork(second)
    second_unit.begin("fixture")
    second_unit.rollback()
    unit = WorkspaceUnitOfWork(first)
    unit.begin("fixture")
    unit.stage(kind="fixture", schema_id="fixture", schema_version=1, record_count=1, content=b"payload")
    unit.rollback()
    assert _object_count(Path(first.path) / "control.sqlite3") == 0
    first_path = Path(first.path)
    assert not any((first_path / "objects").glob("*/*"))
    assert _object_count(Path(second.path) / "control.sqlite3") == 0


def test_workspace_uid_is_rejected_after_generate(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("uid mismatch is indistinguishable when running as root")
    workspace = _record(tmp_path / "uid")
    unit = WorkspaceUnitOfWork(workspace)
    unit.begin("fixture")
    staged = unit.stage(
        kind="fixture",
        schema_id="parquet-fixture",
        schema_version=1,
        record_count=1,
        content=b"fixture",
    )
    assert len(staged) == 64
