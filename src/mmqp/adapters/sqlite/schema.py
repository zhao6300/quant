from __future__ import annotations

import hashlib
import importlib.resources
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

_MIGRATION_NAMES = ("0001_control.sql",)


def read_migration(name: str) -> str:
    """Load a migration script from installed package resources."""
    migration = importlib.resources.files("mmqp.migrations").joinpath(name)
    return migration.read_text(encoding="utf-8")


class SqliteSchema:
    def __init__(self, database: str | Path):
        self.database = Path(database)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def apply_migrations(self, connection: sqlite3.Connection) -> None:
        for name in _MIGRATION_NAMES:
            self._apply_migration(connection, name)

    def _apply_migration(self, connection: sqlite3.Connection, name: str) -> None:
        script = read_migration(name)
        checksum = self._checksum(script)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS migration_history ("
            " migration_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,"
            " checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        existing = connection.execute(
            "SELECT checksum FROM migration_history WHERE name = ?", (name,)
        ).fetchone()
        if existing is None:
            connection.executescript(script)
            connection.execute(
                "INSERT INTO migration_history(name, checksum, applied_at) VALUES (?, ?, ?)",
                (name, checksum, datetime.now(UTC).isoformat()),
            )
        elif existing["checksum"] != checksum:
            raise ValueError("migration checksum mismatch")

    def _checksum(self, script: str) -> str:
        return hashlib.sha256(script.encode("utf-8")).hexdigest()

    def apply(self) -> None:
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("PRAGMA busy_timeout = 5000")
            self.apply_migrations(connection)

    def verify(self) -> None:
        with self.connection() as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("sqlite integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("sqlite foreign key check failed")
