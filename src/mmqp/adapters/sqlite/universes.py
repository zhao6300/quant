from __future__ import annotations

import sqlite3
from builtins import list as list_type
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from mmqp.domain.errors import DomainError, ProblemV1
from mmqp.domain.universes import UniverseMembership, membership_content_id


class SqliteUniverseMembershipRepository:
    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)

    def create(self, membership: UniverseMembership) -> UniverseMembership:
        with self._connection() as connection:
            self._initialize(connection)
            duplicate = connection.execute(
                "SELECT 1 FROM universe_memberships WHERE membership_id = ?",
                (membership.membership_id,),
            ).fetchone()
            if duplicate:
                raise DomainError(
                    ProblemV1(
                        kind="universe/membership-conflict",
                        title="Universe membership conflict",
                        status=409,
                        detail=f"universe membership {membership.membership_id} already exists",
                    )
                )
            connection.execute(
                """
                INSERT INTO universe_memberships
                    (membership_id, universe_version, canonical_asset_id,
                     effective_from, effective_to, membership_source, source_version, content_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    membership.membership_id,
                    membership.universe_version,
                    membership.canonical_asset_id,
                    membership.effective_from.isoformat(),
                    membership.effective_to.isoformat() if membership.effective_to is not None else None,
                    membership.membership_source,
                    membership.source_version,
                    membership_content_id(membership),
                ),
            )
        return membership

    def list(self) -> list_type[UniverseMembership]:
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute(
                """
                SELECT membership_id, universe_version, canonical_asset_id, effective_from,
                       effective_to, membership_source, source_version, content_id
                  FROM universe_memberships
                 ORDER BY effective_from, canonical_asset_id, membership_id
                """
            ).fetchall()
        return [_membership_from_row(row) for row in rows]

    def find(self, membership_id: str) -> UniverseMembership | None:
        with self._connection() as connection:
            self._initialize(connection)
            row = connection.execute(
                "SELECT * FROM universe_memberships WHERE membership_id = ?",
                (membership_id,),
            ).fetchone()
        return _membership_from_row(row) if row is not None else None

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS universe_memberships (
                membership_id TEXT PRIMARY KEY,
                universe_version TEXT NOT NULL,
                canonical_asset_id TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT,
                membership_source TEXT NOT NULL,
                source_version TEXT NOT NULL,
                content_id TEXT NOT NULL,
                UNIQUE (universe_version, canonical_asset_id, effective_from,
                        effective_to, membership_source, source_version)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS universe_memberships_effective_idx ON universe_memberships(effective_from, effective_to)"
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS universe_memberships_immutable_update
            BEFORE UPDATE ON universe_memberships
            BEGIN
                SELECT RAISE(ABORT, 'universe_memberships is immutable');
            END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS universe_memberships_immutable_delete
            BEFORE DELETE ON universe_memberships
            BEGIN
                SELECT RAISE(ABORT, 'universe_memberships is immutable');
            END
            """
        )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


def _membership_from_row(row: sqlite3.Row) -> UniverseMembership:
    return UniverseMembership(
        membership_id=row["membership_id"],
        universe_version=row["universe_version"],
        canonical_asset_id=row["canonical_asset_id"],
        effective_from=date.fromisoformat(row["effective_from"]),
        effective_to=date.fromisoformat(row["effective_to"]) if row["effective_to"] else None,
        membership_source=row["membership_source"],
        source_version=row["source_version"],
    )
