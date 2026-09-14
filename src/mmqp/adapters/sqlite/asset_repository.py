import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from sqlite3 import Connection, Row
from uuid import UUID, uuid4

from mmqp.domain.assets import (
    AssetIdentity,
    AssetVersion,
    MappingOperationError,
    ProviderAssetMapping,
)


class SqliteAssetRegistryRepository:
    """SQLite-backed registry for canonical assets and effective provider mappings."""

    def __init__(self, database: str):
        self._database = str(Path(database))
        Path(self._database).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connection(self) -> Iterator[Connection]:
        connection = sqlite3.connect(self._database, timeout=5)
        connection.row_factory = Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _initialize(connection: Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                market TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                exchange TEXT NOT NULL,
                local_code TEXT NOT NULL,
                name TEXT NOT NULL,
                trading_currency TEXT NOT NULL,
                lifecycle_status TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT,
                predecessor_id TEXT,
                PRIMARY KEY(asset_id, version_id),
                UNIQUE(version_id)
            );
            CREATE INDEX IF NOT EXISTS assets_current
                ON assets(asset_id, effective_to);
            CREATE TRIGGER IF NOT EXISTS assets_immutable_update
                BEFORE UPDATE ON assets
            BEGIN
                SELECT RAISE(ABORT, 'asset versions are immutable');
            END;
            CREATE TRIGGER IF NOT EXISTS assets_immutable_delete
                BEFORE DELETE ON assets
            BEGIN
                SELECT RAISE(ABORT, 'asset versions are immutable');
            END;
            CREATE TABLE IF NOT EXISTS provider_asset_mappings (
                mapping_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                provider_code TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT
            );
            CREATE TABLE IF NOT EXISTS asset_intervals (
                asset_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT,
                predecessor_id TEXT,
                PRIMARY KEY(asset_id, effective_from, version_id)
            );
            CREATE TABLE IF NOT EXISTS asset_successors (
                asset_id TEXT NOT NULL,
                predecessor_id TEXT NOT NULL,
                successor_id TEXT NOT NULL,
                PRIMARY KEY(asset_id, predecessor_id)
            );
            CREATE INDEX IF NOT EXISTS provider_asset_mappings_lookup
                ON provider_asset_mappings(provider, provider_code, effective_from);
            CREATE TRIGGER IF NOT EXISTS provider_asset_mappings_immutable_update
                BEFORE UPDATE ON provider_asset_mappings
            BEGIN
                SELECT RAISE(ABORT, 'provider asset mappings are immutable');
            END;
            CREATE TRIGGER IF NOT EXISTS provider_asset_mappings_immutable_delete
                BEFORE DELETE ON provider_asset_mappings
            BEGIN
                SELECT RAISE(ABORT, 'provider asset mappings are immutable');
            END;
            """
        )

    def find(self, asset_id: str) -> AssetVersion | None:
        with self._connection() as connection:
            self._initialize(connection)
            row = connection.execute(
                """
                SELECT a.*, i.effective_from AS interval_from, i.effective_to AS interval_to
                  FROM assets AS a
                  LEFT JOIN asset_intervals AS i ON i.asset_id = a.asset_id AND i.version_id = a.version_id
                 WHERE a.asset_id = ?
                 ORDER BY i.effective_from DESC,
                          CASE WHEN i.effective_to IS NULL THEN 0 ELSE 1 END,
                          a.version_id
                 LIMIT 1
                """,
                (asset_id,),
            ).fetchone()
        return self._interval_version(row) if row is not None else None

    def as_of(self, asset_id: str, observation_date: date) -> AssetVersion | None:
        observation = observation_date.isoformat()
        with self._connection() as connection:
            self._initialize(connection)
            row = connection.execute(
                """
                SELECT a.*, i.effective_from AS interval_from, i.effective_to AS interval_to
                  FROM assets AS a
                  JOIN asset_intervals AS i ON i.asset_id = a.asset_id AND i.version_id = a.version_id
                 WHERE a.asset_id = ?
                   AND i.effective_from <= ?
                   AND (i.effective_to IS NULL OR i.effective_to >= ?)
                 ORDER BY i.effective_from DESC,
                          CASE WHEN i.effective_to IS NULL THEN 0 ELSE 1 END,
                          a.version_id
                 LIMIT 1
                """,
                (asset_id, observation, observation),
            ).fetchone()
        return self._interval_version(row) if row is not None else None

    def create(self, asset: AssetVersion) -> AssetVersion:
        with self._connection() as connection:
            self._initialize(connection)
            connection.execute(
                """INSERT INTO assets (
                       asset_id, version_id, market, asset_type, exchange,
                       local_code, name, trading_currency, lifecycle_status,
                       effective_from, effective_to, predecessor_id
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    asset.asset_id,
                    asset.version_id,
                    asset.identity.market,
                    asset.identity.asset_type,
                    asset.identity.exchange,
                    asset.identity.local_code,
                    asset.name,
                    asset.trading_currency,
                    asset.lifecycle_status,
                    asset.effective_from.isoformat(),
                    asset.effective_to.isoformat() if asset.effective_to else None,
                    asset.predecessor_id,
                ),
            )
            connection.execute(
                """INSERT INTO asset_intervals (
                       asset_id, version_id, effective_from, effective_to, predecessor_id
                   ) VALUES (?, ?, ?, ?, ?)""",
                (
                    asset.asset_id,
                    asset.version_id,
                    asset.effective_from.isoformat(),
                    asset.effective_to.isoformat() if asset.effective_to else None,
                    asset.predecessor_id,
                ),
            )
        return asset

    def close(self, asset_id: str, effective_end: date) -> AssetVersion | None:
        del asset_id, effective_end
        return None

    def history(self, asset_id: str) -> list[AssetVersion]:
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute(
                """
                SELECT a.*, i.effective_from AS interval_from, i.effective_to AS interval_to
                  FROM assets AS a
                  JOIN asset_intervals AS i ON i.asset_id = a.asset_id AND i.version_id = a.version_id
                 WHERE a.asset_id = ?
                 GROUP BY a.asset_id, i.version_id
                 ORDER BY MAX(i.effective_from),
                          MAX(CASE WHEN i.version_id IS NULL THEN 1 ELSE 0 END),
                          a.version_id
                """,
                (asset_id,),
            ).fetchall()
        return [self._interval_version(row) for row in rows]

    def current(self) -> list[AssetVersion]:
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute(
                """
                SELECT a.*, i.effective_from AS interval_from, i.effective_to AS interval_to
                  FROM assets AS a
                  JOIN asset_intervals AS i ON i.asset_id = a.asset_id AND i.version_id = a.version_id
                 WHERE i.effective_to IS NULL
                 GROUP BY a.asset_id
                 HAVING MAX(i.effective_from)
                 ORDER BY a.asset_id, a.version_id
                """
            ).fetchall()
        return [self._interval_version(row) for row in rows]

    def create_provider_mapping(self, mapping: ProviderAssetMapping) -> ProviderAssetMapping:
        with self._connection() as connection:
            self._initialize(connection)
            existing_row = connection.execute(
                """
                SELECT * FROM provider_asset_mappings
                 WHERE provider = ?
                   AND provider_code = ?
                   AND asset_id = ?
                   AND effective_from = ?
                   AND effective_to IS ?
                """,
                (
                    mapping.provider,
                    mapping.provider_code,
                    mapping.asset_id,
                    mapping.effective_from.isoformat(),
                    mapping.effective_to.isoformat() if mapping.effective_to else None,
                ),
            ).fetchone()
            if existing_row is not None:
                return self._mapping_from(existing_row)
            mapping_id = mapping.mapping_id if mapping.mapping_id is not None else uuid4()
            try:
                connection.execute(
                    """INSERT INTO provider_asset_mappings (
                           mapping_id, provider, provider_code, asset_id,
                           effective_from, effective_to
                       ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        str(mapping_id),
                        mapping.provider,
                        mapping.provider_code,
                        mapping.asset_id,
                        mapping.effective_from.isoformat(),
                        mapping.effective_to.isoformat() if mapping.effective_to else None,
                    ),
                )
            except Exception as error:
                raise MappingOperationError(
                    status=409,
                    title="Provider asset mapping conflict",
                    detail="provider asset mapping could not be created",
                ) from error
        return ProviderAssetMapping(
            mapping_id=mapping_id,
            provider=mapping.provider,
            provider_code=mapping.provider_code,
            asset_id=mapping.asset_id,
            effective_from=mapping.effective_from,
            effective_to=mapping.effective_to,
        )

    def provider_mapping_by_id(self, mapping_id: UUID) -> ProviderAssetMapping | None:
        with self._connection() as connection:
            self._initialize(connection)
            row = connection.execute(
                "SELECT * FROM provider_asset_mappings WHERE mapping_id = ?",
                (str(mapping_id),),
            ).fetchone()
        return self._mapping_from(row) if row is not None else None

    def provider_mappings(
        self,
        *,
        provider: str,
        provider_code: str,
        observation_date: date,
    ) -> list[ProviderAssetMapping]:
        observation = observation_date.isoformat()
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute(
                """
                SELECT *
                  FROM provider_asset_mappings
                 WHERE provider = ?
                   AND provider_code = ?
                   AND effective_from <= ?
                   AND (effective_to IS NULL OR effective_to >= ?)
                 ORDER BY effective_from, asset_id, mapping_id
                """,
                (provider, provider_code, observation, observation),
            ).fetchall()
        return [self._mapping_from(row) for row in rows]

    @staticmethod
    @staticmethod
    def _asset_version(row: Row) -> AssetVersion:
        observation_date = row["effective_to"]
        identity = AssetIdentity(
            market=row["market"],
            asset_type=row["asset_type"],
            exchange=row["exchange"],
            local_code=row["local_code"],
        )
        return AssetVersion(
            version_id=row["version_id"],
            asset_id=row["asset_id"],
            identity=identity,
            name=row["name"],
            trading_currency=row["trading_currency"],
            lifecycle_status=row["lifecycle_status"],
            effective_from=date.fromisoformat(row["effective_from"]),
            effective_to=(date.fromisoformat(observation_date) if observation_date is not None else None),
            predecessor_id=row["predecessor_id"],
        )

    @staticmethod
    def _interval_version(row: Row) -> AssetVersion:
        return AssetVersion(
            version_id=row["version_id"],
            asset_id=row["asset_id"],
            identity=AssetIdentity(
                market=row["market"],
                asset_type=row["asset_type"],
                exchange=row["exchange"],
                local_code=row["local_code"],
            ),
            name=row["name"],
            trading_currency=row["trading_currency"],
            lifecycle_status=row["lifecycle_status"],
            effective_from=date.fromisoformat(row["interval_from"]),
            effective_to=(date.fromisoformat(row["interval_to"]) if row["interval_to"] is not None else None),
            predecessor_id=row["predecessor_id"],
        )

    @staticmethod
    def _mapping_from(row: Row) -> ProviderAssetMapping:
        return ProviderAssetMapping(
            mapping_id=UUID(row["mapping_id"]),
            provider=row["provider"],
            provider_code=row["provider_code"],
            asset_id=row["asset_id"],
            effective_from=date.fromisoformat(row["effective_from"]),
            effective_to=(
                date.fromisoformat(row["effective_to"]) if row["effective_to"] is not None else None
            ),
        )
