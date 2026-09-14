import sqlite3
from builtins import list as list_type
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, time
from pathlib import Path

from mmqp.domain.calendars import (
    TradingCalendarDay,
    TradingCalendarVersion,
    TradingSession,
    ValuationCalendarVersion,
)
from mmqp.domain.errors import DomainError, ProblemV1


class SqliteTradingCalendarRepository:
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

    def create(self, version: TradingCalendarVersion) -> TradingCalendarVersion:
        with self._connection() as connection:
            self._initialize(connection)
            if connection.execute(
                "SELECT 1 FROM trading_calendar_versions WHERE version_id = ?", (version.version_id,)
            ).fetchone():
                raise DomainError(
                    ProblemV1(
                        kind="calendar/version-conflict",
                        title="Calendar version conflict",
                        status=409,
                        detail=f"calendar version {version.version_id} already exists",
                    )
                )
            connection.execute(
                """
                INSERT INTO trading_calendar_versions
                    (version_id, market, exchange, timezone, effective_from, effective_to)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                _trading_header_values(version),
            )
            connection.executemany(
                """
                INSERT INTO trading_calendar_days
                    (version_id, market, exchange, calendar_date, day_kind)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (version.version_id, day.market, day.exchange, day.date.isoformat(), day.kind)
                    for day in version.days
                ],
            )
            connection.executemany(
                """
                INSERT INTO trading_calendar_sessions
                    (version_id, calendar_date, position, session_kind, start_time, end_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                _session_values(version),
            )
        return version

    def list(
        self, market: str | None = None, exchange: str | None = None
    ) -> list_type[TradingCalendarVersion]:
        with self._connection() as connection:
            self._initialize(connection)
            predicates: list[str] = []
            values: list[str] = []
            if market is not None:
                predicates.append("market = ?")
                values.append(market)
            if exchange is not None:
                predicates.append("exchange = ?")
                values.append(exchange)
            predicate = "WHERE " + " AND ".join(predicates) if predicates else ""
            rows = connection.execute(
                f"SELECT * FROM trading_calendar_versions {predicate} ORDER BY effective_from, version_id",
                values,
            ).fetchall()
            return [_trading_from_header(connection, row) for row in rows]

    def select(self, market: str, exchange: str, as_of: date) -> list_type[TradingCalendarVersion]:
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute(
                """
                SELECT h.* FROM trading_calendar_versions h
                JOIN trading_calendar_days d ON d.version_id = h.version_id
                WHERE h.market = ?
                  AND h.exchange = ?
                  AND d.calendar_date = ?
                 ORDER BY h.version_id
                """,
                (market, exchange, as_of.isoformat()),
            ).fetchall()
            if rows:
                return [_trading_from_header(connection, row) for row in rows]
            rows = connection.execute(
                """
                SELECT * FROM trading_calendar_versions
                 WHERE market = ?
                   AND exchange = ?
                   AND effective_from <= ?
                   AND (effective_to IS NULL OR effective_to >= ?)
                 ORDER BY version_id
                """,
                (market, exchange, as_of.isoformat(), as_of.isoformat()),
            ).fetchall()
            return [_trading_from_header(connection, row) for row in rows]

    def close(self) -> None:
        return None

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_calendar_versions (
                version_id TEXT PRIMARY KEY,
                market TEXT NOT NULL,
                exchange TEXT NOT NULL,
                timezone TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_calendar_days (
                version_id TEXT NOT NULL,
                market TEXT NOT NULL,
                exchange TEXT NOT NULL,
                calendar_date TEXT NOT NULL,
                day_kind TEXT NOT NULL,
                PRIMARY KEY (version_id, calendar_date),
                FOREIGN KEY (version_id, market, exchange)
                    REFERENCES trading_calendar_versions(version_id, market, exchange)
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS trading_calendar_versions_identity
                ON trading_calendar_versions(version_id, market, exchange)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trading_calendar_sessions (
                version_id TEXT NOT NULL,
                calendar_date TEXT NOT NULL,
                position INTEGER NOT NULL CHECK (position >= 0),
                session_kind TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                PRIMARY KEY (version_id, calendar_date, position),
                FOREIGN KEY (version_id, calendar_date)
                    REFERENCES trading_calendar_days(version_id, calendar_date)
            )
            """
        )
        for table, immutable_columns in (
            ("trading_calendar_versions", "market, exchange, timezone, effective_from, effective_to"),
            ("trading_calendar_days", "market, exchange, day_kind"),
            ("trading_calendar_sessions", "session_kind, start_time, end_time"),
        ):
            connection.execute(
                f"""
            CREATE TRIGGER IF NOT EXISTS {table}_immutable_update
                BEFORE UPDATE OF {immutable_columns} ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is immutable');
            END
            """
            )
            connection.execute(
                f"""
            CREATE TRIGGER IF NOT EXISTS {table}_immutable_delete
                BEFORE DELETE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is immutable');
            END
            """
            )


class SqliteValuationCalendarRepository:
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

    def create(self, version: ValuationCalendarVersion) -> ValuationCalendarVersion:
        with self._connection() as connection:
            self._initialize(connection)
            if connection.execute(
                "SELECT 1 FROM valuation_calendars WHERE version_id = ?", (version.version_id,)
            ).fetchone():
                raise DomainError(
                    ProblemV1(
                        kind="calendar/valuation-version-conflict",
                        title="Valuation calendar version conflict",
                        status=409,
                        detail=f"valuation calendar version {version.version_id} already exists",
                    )
                )
            connection.execute(
                """
                INSERT INTO valuation_calendars
                    (version_id, market, timezone, effective_from, effective_to)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    version.version_id,
                    version.market,
                    version.timezone,
                    version.effective_from.isoformat(),
                    version.effective_to.isoformat() if version.effective_to else None,
                ),
            )
        return version

    def list(self, market: str | None = None) -> list_type[ValuationCalendarVersion]:
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute(
                "SELECT * FROM valuation_calendars WHERE (? IS NULL OR market = ?) ORDER BY market, effective_from",
                (market, market),
            ).fetchall()
        return [_valuation_from_row(row) for row in rows]

    def select(self, market: str, as_of: date) -> list_type[ValuationCalendarVersion]:
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute(
                """
                SELECT * FROM valuation_calendars
                 WHERE market = ?
                   AND effective_from <= ?
                   AND (effective_to IS NULL OR effective_to >= ?)
                 ORDER BY version_id
                """,
                (market, as_of.isoformat(), as_of.isoformat()),
            ).fetchall()
        return [_valuation_from_row(row) for row in rows]

    def close(self) -> None:
        return None

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS valuation_calendars (
                version_id TEXT PRIMARY KEY,
                market TEXT NOT NULL,
                timezone TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS valuation_calendars_immutable_update
                BEFORE UPDATE OF market, timezone, effective_from, effective_to
                ON valuation_calendars
            BEGIN
                SELECT RAISE(ABORT, 'valuation_calendars is immutable');
            END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS valuation_calendars_immutable_delete
                BEFORE DELETE ON valuation_calendars
            BEGIN
                SELECT RAISE(ABORT, 'valuation_calendars is immutable');
            END
            """
        )


def _trading_header_values(
    version: TradingCalendarVersion,
) -> tuple[str, str, str, str, str, str | None]:
    return (
        version.version_id,
        version.market,
        version.exchange,
        version.timezone,
        version.effective_from.isoformat(),
        version.effective_to.isoformat() if version.effective_to else None,
    )


def _session_values(version: TradingCalendarVersion) -> list[tuple[str, str, int, str, str, str]]:
    values: list[tuple[str, str, int, str, str, str]] = []
    for day in version.days:
        for position, session in enumerate(day.sessions):
            values.append(
                (
                    version.version_id,
                    day.date.isoformat(),
                    position,
                    session.kind,
                    session.start,
                    session.end,
                )
            )
    return values


def _trading_from_header(connection: sqlite3.Connection, header: sqlite3.Row) -> TradingCalendarVersion:
    day_rows = connection.execute(
        """
        SELECT * FROM trading_calendar_days WHERE version_id = ? ORDER BY calendar_date
        """,
        (header["version_id"],),
    ).fetchall()
    sessions_by_date: dict[str, list[TradingSession]] = {}
    for session_row in connection.execute(
        """
        SELECT * FROM trading_calendar_sessions WHERE version_id = ?
         ORDER BY calendar_date, position
        """,
        (header["version_id"],),
    ):
        sessions_by_date.setdefault(session_row["calendar_date"], []).append(
            TradingSession(
                start=_time_text(time.fromisoformat(session_row["start_time"])),
                end=_time_text(time.fromisoformat(session_row["end_time"])),
                kind=session_row["session_kind"],
            )
        )
    days = tuple(
        TradingCalendarDay(
            market=day_row["market"],
            exchange=day_row["exchange"],
            date=date.fromisoformat(day_row["calendar_date"]),
            kind=day_row["day_kind"],
            sessions=tuple(sessions_by_date.get(day_row["calendar_date"], ())),
        )
        for day_row in day_rows
    )
    return TradingCalendarVersion(
        version_id=header["version_id"],
        market=header["market"],
        exchange=header["exchange"],
        timezone=header["timezone"],
        effective_from=date.fromisoformat(header["effective_from"]),
        effective_to=date.fromisoformat(header["effective_to"]) if header["effective_to"] else None,
        days=days,
    )


def _valuation_from_row(row: sqlite3.Row) -> ValuationCalendarVersion:
    return ValuationCalendarVersion(
        version_id=row["version_id"],
        market=row["market"],
        timezone=row["timezone"],
        effective_from=date.fromisoformat(row["effective_from"]),
        effective_to=date.fromisoformat(row["effective_to"]) if row["effective_to"] else None,
    )


def _time_text(value: time) -> str:
    return value.isoformat(timespec="minutes")
