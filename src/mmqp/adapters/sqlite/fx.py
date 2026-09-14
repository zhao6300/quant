import sqlite3
from builtins import list as list_type
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

from mmqp.domain.fx import FXRate


class SqliteFXRateRepository:
    def __init__(self, database: str):
        self._database = database

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            self._initialize(connection)
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def close(self) -> None:
        return None

    def create(self, rate: FXRate) -> FXRate:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO fx_rates
                    (version_id, source_currency, target_currency, rate_date, rate, provider,
                     provider_pair, retrieved_at, provenance_id, data_version_id,
                     direct_source_version_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rate.version_id,
                    rate.source_currency,
                    rate.target_currency,
                    rate.rate_date.isoformat(),
                    format(rate.rate, "f"),
                    rate.provider,
                    rate.provider_pair,
                    rate.retrieved_at.isoformat(),
                    rate.provenance_id,
                    rate.data_version_id,
                    rate.direct_source_version_id,
                ),
            )
        return rate

    def select(
        self,
        source_currency: str,
        target_currency: str,
        rate_dates: tuple[date, ...],
    ) -> list_type[FXRate]:
        placeholders = ",".join("?" for _ in rate_dates)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM fx_rates
                WHERE source_currency = ? AND target_currency = ? AND rate_date IN ({placeholders})
                """,
                (source_currency, target_currency, *(value.isoformat() for value in rate_dates)),
            ).fetchall()
        return [_rate(row) for row in rows]

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS fx_rates (
                version_id TEXT PRIMARY KEY,
                source_currency TEXT NOT NULL,
                target_currency TEXT NOT NULL,
                rate_date TEXT NOT NULL,
                rate TEXT NOT NULL,
                provider TEXT NOT NULL,
                provider_pair TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                provenance_id TEXT NOT NULL,
                data_version_id TEXT NOT NULL,
                direct_source_version_id TEXT,
                UNIQUE(source_currency, target_currency, rate_date, version_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS fx_rates_immutable_update
                BEFORE UPDATE ON fx_rates
            BEGIN SELECT RAISE(ABORT, 'fx_rates is immutable'); END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS fx_rates_immutable_delete
                BEFORE DELETE ON fx_rates
            BEGIN SELECT RAISE(ABORT, 'fx_rates is immutable'); END
            """
        )


def _rate(row: sqlite3.Row) -> FXRate:
    return FXRate(
        version_id=row["version_id"],
        source_currency=row["source_currency"],
        target_currency=row["target_currency"],
        rate_date=date.fromisoformat(row["rate_date"]),
        rate=Decimal(row["rate"]),
        provider=row["provider"],
        provider_pair=row["provider_pair"],
        retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
        provenance_id=row["provenance_id"],
        data_version_id=row["data_version_id"],
        direct_source_version_id=row["direct_source_version_id"],
    )
