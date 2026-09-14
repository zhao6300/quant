from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.adapters.sqlite.workspace_repository import SqliteWorkspaceRepository
from mmqp.application.workspaces import WorkspaceService
from mmqp.domain.workspace import WorkspaceConflictError


@settings(max_examples=100, deadline=None)
@given(
    first=st.integers(min_value=1),
    second=st.integers(min_value=1),
)
def test_workspace_paths_never_overlap(first: int, second: int) -> None:
    with TemporaryDirectory() as base:
        first_workspace = Path(base) / f"first-{first}"
        second_workspace = Path(base) / f"second-{second}"
        service = WorkspaceService(SqliteWorkspaceRepository(Path(base) / "workspaces.sqlite3"))
        first_record = service.create(str(first_workspace), "First")
        second_record = service.create(str(second_workspace), "Second")

        assert first_record.path != second_record.path
        with pytest.raises(WorkspaceConflictError):
            service.create(str(first_workspace / "nested"), "Overlap")
