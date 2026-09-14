import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from mmqp.domain.workspace import WorkspaceRecord

SCHEMA_VERSION = 1


class SqliteWorkspaceRepository:
    def __init__(self, db_path: os.PathLike[str] | str):
        self._db_path = Path(db_path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                bound_uid INTEGER NOT NULL,
                created_at TEXT NOT NULL
            ) """
        )
        connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL UNIQUE)")
        connection.execute("INSERT OR IGNORE INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))

    def create(self, workspace: WorkspaceRecord) -> WorkspaceRecord:
        with self._connection() as connection:
            self._initialize(connection)
            connection.execute(
                "INSERT INTO workspaces VALUES (?, ?, ?, ?, ?)",
                (
                    workspace.id,
                    workspace.path,
                    workspace.display_name,
                    workspace.bound_uid,
                    workspace.created_at.isoformat() if workspace.created_at else None,
                ),
            )
        return workspace

    def get(self, workspace_id: str) -> WorkspaceRecord | None:
        with self._connection() as connection:
            self._initialize(connection)
            row = connection.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        return self._to_record(row) if row is not None else None

    def get_by_path(self, path: str) -> WorkspaceRecord | None:
        with self._connection() as connection:
            self._initialize(connection)
            row = connection.execute("SELECT * FROM workspaces WHERE path = ?", (path,)).fetchone()
        return self._to_record(row) if row is not None else None

    def list(self) -> list[WorkspaceRecord]:
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute("SELECT * FROM workspaces ORDER BY created_at").fetchall()
        return [self._to_record(row) for row in rows]

    @staticmethod
    def _to_record(row: sqlite3.Row) -> WorkspaceRecord:
        return WorkspaceRecord(
            id=row["id"],
            path=row["path"],
            display_name=row["display_name"],
            bound_uid=row["bound_uid"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
