from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from mmqp.adapters.sqlite.schema import SqliteSchema
from mmqp.ports.stable import CreateWorkspaceV1, WorkspaceRefV1


class WorkspaceRecord(Protocol):
    workspace_id: str
    canonical_path: str
    bound_uid: int
    created_at: str
    format_version: int


class SqliteControlWorkspaceRepository:
    """Baseline SQLite control-plane repository."""

    def __init__(self, database: str | Path):
        self._schema = SqliteSchema(database)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        with self._schema.connection() as connection:
            self._schema.apply_migrations(connection)
            yield connection

    def create(self, request: CreateWorkspaceV1, bound_uid: int) -> WorkspaceRefV1:
        with self._connection() as connection:
            workspace_id = uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO workspace
                (workspace_id, canonical_path, bound_uid, created_at, format_version)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    request.path,
                    bound_uid,
                    datetime.now(UTC).isoformat(),
                    1,
                ),
            )
            return WorkspaceRefV1(workspace_id=workspace_id, path=request.path)

    def all(self) -> list[WorkspaceRefV1]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT workspace_id, canonical_path FROM workspace ORDER BY created_at"
            ).fetchall()
            return [WorkspaceRefV1(workspace_id=str(row[0]), path=str(row[1])) for row in rows]
