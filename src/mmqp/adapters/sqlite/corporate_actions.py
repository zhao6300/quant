from __future__ import annotations

import json
import sqlite3
from builtins import list as list_type
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from mmqp.domain.corporate_actions import CorporateActionVersion
from mmqp.domain.errors import DomainError, ProblemV1


class SqliteCorporateActionRepository:
    def __init__(self, db_path: str | Path):
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
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create(self, action: CorporateActionVersion) -> CorporateActionVersion:
        with self._connection() as connection:
            self._initialize(connection)
            duplicate = connection.execute(
                "SELECT 1 FROM corporate_action_versions WHERE version_id = ?",
                (action.version_id,),
            ).fetchone()
            if duplicate:
                raise DomainError(
                    ProblemV1(
                        kind="corporate-action/version-conflict",
                        title="Corporate-action version conflict",
                        status=409,
                        detail=f"corporate action version {action.version_id} already exists",
                    )
                )
            connection.execute(
                """INSERT INTO corporate_action_versions
                    (version_id, canonical_asset_id, event_id, action_type,
                     announcement_date, ex_date, record_date, effective_date,
                     terms_json, provenance_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    action.version_id,
                    action.canonical_asset_id,
                    action.event_id,
                    action.action_type,
                    action.announcement_date.isoformat(),
                    action.ex_date.isoformat(),
                    action.record_date.isoformat() if action.record_date else None,
                    action.effective_date.isoformat(),
                    json.dumps(action.terms, sort_keys=True),
                    action.provenance_id,
                ),
            )
        return action

    def list(self) -> list_type[CorporateActionVersion]:
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute(
                "SELECT * FROM corporate_action_versions ORDER BY ex_date, version_id"
            ).fetchall()
        return [_from_row(row) for row in rows]

    def close(self) -> None:
        return None

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS corporate_action_versions (
                version_id TEXT PRIMARY KEY,
                canonical_asset_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                announcement_date TEXT NOT NULL,
                ex_date TEXT NOT NULL,
                record_date TEXT,
                effective_date TEXT NOT NULL,
                terms_json TEXT NOT NULL,
                provenance_id TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TRIGGER IF NOT EXISTS corporate_action_versions_immutable_update
            BEFORE UPDATE ON corporate_action_versions
            BEGIN
                SELECT RAISE(ABORT, 'corporate_action_versions is immutable');
            END
            """
        )
        connection.execute(
            """CREATE TRIGGER IF NOT EXISTS corporate_action_versions_immutable_delete
            BEFORE DELETE ON corporate_action_versions
            BEGIN
                SELECT RAISE(ABORT, 'corporate_action_versions is immutable');
            END
            """
        )


def _from_row(row: sqlite3.Row) -> CorporateActionVersion:
    terms_raw = json.loads(row["terms_json"])
    terms = mapping_from_raw(terms_raw)
    return CorporateActionVersion(
        version_id=row["version_id"],
        canonical_asset_id=row["canonical_asset_id"],
        event_id=row["event_id"],
        action_type=row["action_type"],
        announcement_date=date.fromisoformat(row["announcement_date"]),
        ex_date=date.fromisoformat(row["ex_date"]),
        record_date=date.fromisoformat(row["record_date"]) if row["record_date"] else None,
        effective_date=date.fromisoformat(row["effective_date"]),
        terms=terms,
        provenance_id=row["provenance_id"],
    )


def mapping_from_raw(raw: object) -> Mapping[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}
