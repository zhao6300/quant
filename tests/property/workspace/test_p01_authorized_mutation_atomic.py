import hashlib
import os
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.adapters.sqlite.workspace_repository import SqliteWorkspaceRepository
from mmqp.application.uow import WorkspaceUnitOfWork
from mmqp.application.workspaces import WorkspaceService
from mmqp.domain.workspace import WorkspaceRecord

# Feature: multi-market-quant-platform, Property 1: Authorized mutation is atomic


def _workspace_record(root: Path) -> WorkspaceRecord:
    service = WorkspaceService(SqliteWorkspaceRepository(root / "workspaces.sqlite3"))
    return service.create(str(root / "workspace"), "Property 1")


def _database_state(path: Path) -> tuple[tuple[object, ...], ...]:
    with sqlite3.connect(path) as connection:
        return tuple(
            row
            for table in ("workspace_operations", "workspace_objects", "workspace_object_links")
            for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1, 2, 3")
        )


def _filesystem_state(root: Path) -> tuple[tuple[str, int, str], ...]:
    files: list[tuple[str, int, str]] = []
    for path in root.rglob("*"):
        if path.is_file():
            files.append(
                (
                    path.relative_to(root).as_posix(),
                    path.stat().st_size,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
    return tuple(files)


def _complete_state(
    workspace: WorkspaceRecord,
) -> tuple[str, tuple[object, ...], tuple[tuple[str, int, str], ...]]:
    workspace_path = Path(workspace.path)
    return (
        workspace_path.as_posix(),
        _database_state(workspace_path / "control.sqlite3"),
        _filesystem_state(workspace_path),
    )


def _stage_commands(unit: WorkspaceUnitOfWork, commands: Iterator[tuple[int, bytes]]) -> None:
    for operation_index, (schema_version, content) in enumerate(commands):
        unit.stage(
            kind="fixture",
            schema_id="fixture-binary-v1",
            schema_version=schema_version,
            record_count=1,
            content=content,
        )
        if operation_index == 0:
            raise OSError("injected mutation failure")


@settings(max_examples=100, deadline=None)
@given(
    command_count=st.integers(min_value=1, max_value=3),
    command_kind=st.sampled_from(("catalog-command", "identity-command")),
)
def test_authorized_mutation_is_atomic(command_count: int, command_kind: str) -> None:
    with TemporaryDirectory() as temporary:
        workspace = _workspace_record(Path(temporary))
        unit = WorkspaceUnitOfWork(workspace)
        unit.begin(command_kind)
        unit.stage(
            kind="fixture",
            schema_id="fixture-binary-v1",
            schema_version=1,
            record_count=1,
            content=b"baseline",
        )
        unit.commit()

        Path(workspace.path) / "control.sqlite3"
        state_before = _complete_state(workspace)
        commands = iter((index + 1, f"command-{index}".encode()) for index in range(command_count))
        if command_kind == "identity-command":
            unauthorized = replace(workspace, bound_uid=os.geteuid() + 1)
            with pytest.raises(Exception, match="current uid does not match bound uid"):
                WorkspaceUnitOfWork(unauthorized).begin(command_kind)
        else:
            doomed = WorkspaceUnitOfWork(workspace)
            doomed.begin(command_kind)
            with pytest.raises(OSError, match="injected mutation failure"):
                _stage_commands(doomed, commands)
            doomed.rollback()

        assert _complete_state(workspace) == state_before
