import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from mmqp.domain.compliance import ComplianceProfileVersionV1


class SqliteComplianceRepository:
    def __init__(self, database: str | Path):
        self._database = str(Path(database))

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            self._initialize(connection)
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS compliance_profile_versions (
                version_id TEXT PRIMARY KEY,
                provider_name TEXT NOT NULL,
                account_type TEXT NOT NULL,
                data_categories TEXT NOT NULL,
                permitted_purposes TEXT NOT NULL,
                retention_permissions TEXT NOT NULL,
                export_permissions TEXT NOT NULL,
                confirmed_at TEXT NOT NULL,
                predecessor_id TEXT,
                created_at TEXT NOT NULL,
                content_id TEXT NOT NULL,
                UNIQUE(provider_name, content_id)
            );
            CREATE TABLE IF NOT EXISTS current_compliance_profiles (
                provider_name TEXT PRIMARY KEY,
                version_id TEXT NOT NULL,
                FOREIGN KEY(version_id) REFERENCES compliance_profile_versions(version_id)
            );
            CREATE TRIGGER IF NOT EXISTS compliance_profile_versions_immutable_update
                BEFORE UPDATE ON compliance_profile_versions
            BEGIN
                SELECT RAISE(ABORT, 'compliance profile versions are immutable');
            END;
            CREATE TRIGGER IF NOT EXISTS compliance_profile_versions_immutable_delete
                BEFORE DELETE ON compliance_profile_versions
            BEGIN
                SELECT RAISE(ABORT, 'compliance profile versions are immutable');
            END;
            """
        )

    def get_current(self, provider_name: str) -> ComplianceProfileVersionV1 | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT v.*
                FROM current_compliance_profiles c
                JOIN compliance_profile_versions v
                  ON v.version_id = c.version_id
                WHERE c.provider_name = ?
                """,
                (provider_name,),
            ).fetchone()
        return None if row is None else _profile(row)

    def save_profile(self, profile: ComplianceProfileVersionV1) -> None:
        with self._connection() as connection:
            predecessor = profile.predecessor_id
            if predecessor is not None:
                row = connection.execute(
                    "SELECT provider_name FROM compliance_profile_versions WHERE version_id = ?",
                    (predecessor,),
                ).fetchone()
                if row is None or row["provider_name"] != profile.provider_name:
                    raise ValueError("compliance predecessor must be from the same provider")
            content = _content_id(profile)
            created_at = datetime.now().isoformat()
            connection.execute(
                """
                INSERT INTO compliance_profile_versions
                    (
                        version_id, provider_name, account_type, data_categories,
                        permitted_purposes, retention_permissions, export_permissions,
                        confirmed_at, predecessor_id, created_at, content_id
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(version_id) DO NOTHING
                """,
                (
                    profile.version_id,
                    profile.provider_name,
                    profile.account_type,
                    json.dumps(profile.data_categories, sort_keys=True),
                    json.dumps(profile.permitted_purposes, sort_keys=True),
                    json.dumps(profile.retention_permissions, sort_keys=True),
                    json.dumps(profile.export_permissions, sort_keys=True),
                    profile.confirmed_at.isoformat(),
                    profile.predecessor_id,
                    created_at,
                    content,
                ),
            )
            connection.execute(
                """
                INSERT INTO current_compliance_profiles(provider_name, version_id)
                VALUES (?, ?)
                ON CONFLICT(provider_name) DO UPDATE
                SET version_id = excluded.version_id
                """,
                (profile.provider_name, profile.version_id),
            )

    def history(self, provider_name: str) -> tuple[ComplianceProfileVersionV1, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT v.*
                FROM compliance_profile_versions v
                WHERE v.provider_name = ?
                ORDER BY v.confirmed_at, v.created_at, v.version_id
                """,
                (provider_name,),
            ).fetchall()
        return tuple(_profile(row) for row in rows)


def _content_id(profile: ComplianceProfileVersionV1) -> str:
    payload = {
        "account_type": profile.account_type,
        "confirmed_at": profile.confirmed_at.isoformat(),
        "data_categories": profile.data_categories,
        "export_permissions": profile.export_permissions,
        "permitted_purposes": profile.permitted_purposes,
        "predecessor_id": profile.predecessor_id,
        "provider_name": profile.provider_name,
        "retention_permissions": profile.retention_permissions,
        "version_id": profile.version_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _profile(row: Any) -> ComplianceProfileVersionV1:
    return ComplianceProfileVersionV1(
        provider_name=row["provider_name"],
        account_type=row["account_type"],
        data_categories=tuple(json.loads(row["data_categories"])),
        permitted_purposes=tuple(json.loads(row["permitted_purposes"])),
        retention_permissions=json.loads(row["retention_permissions"]),
        export_permissions=json.loads(row["export_permissions"]),
        confirmed_at=datetime.fromisoformat(row["confirmed_at"]),
        version_id=row["version_id"],
        predecessor_id=row["predecessor_id"],
    )
