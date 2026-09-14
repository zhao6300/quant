import sqlite3
from builtins import list as list_type
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast

from mmqp.domain.errors import DomainError, ProblemV1
from mmqp.domain.market_rules import (
    MarketRuleProfile,
    PriceLimitRule,
    SellAvailabilityRule,
    SessionKind,
)


class SqliteMarketRuleRepository:
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

    def create(self, profile: MarketRuleProfile) -> MarketRuleProfile:
        with self._connection() as connection:
            self._initialize(connection)
            if connection.execute(
                "SELECT 1 FROM market_rule_profiles WHERE version_id = ?", (profile.version_id,)
            ).fetchone():
                raise DomainError(
                    ProblemV1(
                        kind="market-rule/profile-conflict",
                        title="Market-rule profile conflict",
                        status=409,
                        detail=f"market-rule profile {profile.version_id} already exists",
                    )
                )
            connection.execute(
                """
                INSERT INTO market_rule_profiles
                    (version_id, market, exchange, asset_type, effective_from, effective_to,
                     trading_lot, tick_size, price_limit_rule, price_limit_percent,
                     sell_availability_rule, security_settlement_open_dates,
                     cash_settlement_open_dates, permitted_session_types)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _row_values(profile),
            )
        return profile

    def list(
        self,
        market: str | None = None,
        exchange: str | None = None,
        asset_type: str | None = None,
    ) -> list_type[MarketRuleProfile]:
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute(
                """
                SELECT * FROM market_rule_profiles
                 WHERE (? IS NULL OR market = ?)
                   AND (? IS NULL OR exchange = ?)
                   AND (? IS NULL OR asset_type = ?)
                 ORDER BY market, exchange, asset_type, effective_from, version_id
                """,
                (market, market, exchange, exchange, asset_type, asset_type),
            ).fetchall()
        return [_profile(row) for row in rows]

    def select(
        self, market: str, exchange: str, asset_type: str, as_of: date
    ) -> list_type[MarketRuleProfile]:
        with self._connection() as connection:
            self._initialize(connection)
            rows = connection.execute(
                """
                SELECT * FROM market_rule_profiles
                 WHERE market = ?
                   AND exchange = ?
                   AND asset_type = ?
                   AND effective_from <= ?
                   AND (effective_to IS NULL OR effective_to >= ?)
                 ORDER BY version_id
                """,
                (market, exchange, asset_type, as_of.isoformat(), as_of.isoformat()),
            ).fetchall()
        return [_profile(row) for row in rows]

    def close(self) -> None:
        return None

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS market_rule_profiles (
                version_id TEXT PRIMARY KEY,
                market TEXT NOT NULL,
                exchange TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                effective_to TEXT,
                trading_lot INTEGER NOT NULL,
                tick_size TEXT NOT NULL,
                price_limit_rule TEXT NOT NULL,
                price_limit_percent TEXT,
                sell_availability_rule TEXT NOT NULL,
                security_settlement_open_dates INTEGER NOT NULL,
                cash_settlement_open_dates INTEGER NOT NULL,
                permitted_session_types TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS market_rule_profiles_immutable_update
                BEFORE UPDATE ON market_rule_profiles
            BEGIN
                SELECT RAISE(ABORT, 'market_rule_profiles is immutable');
            END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS market_rule_profiles_immutable_delete
                BEFORE DELETE ON market_rule_profiles
            BEGIN
                SELECT RAISE(ABORT, 'market_rule_profiles is immutable');
            END
            """
        )


def _row_values(
    profile: MarketRuleProfile,
) -> tuple[str, str, str, str, str, str | None, int, str, str, str | None, str, int, int, str]:
    return (
        profile.version_id,
        profile.market,
        profile.exchange,
        profile.asset_type,
        profile.effective_from.isoformat(),
        profile.effective_to.isoformat() if profile.effective_to else None,
        profile.trading_lot,
        str(profile.tick_size),
        profile.price_limit_rule,
        str(profile.price_limit_percent) if profile.price_limit_percent is not None else None,
        profile.sell_availability_rule,
        profile.security_settlement_open_dates,
        profile.cash_settlement_open_dates,
        "|".join(profile.permitted_session_types),
    )


def _profile(row: sqlite3.Row) -> MarketRuleProfile:
    price_limit_rule = row["price_limit_rule"]
    assert isinstance(price_limit_rule, str)
    return MarketRuleProfile(
        version_id=row["version_id"],
        market=row["market"],
        exchange=row["exchange"],
        asset_type=row["asset_type"],
        effective_from=date.fromisoformat(row["effective_from"]),
        effective_to=date.fromisoformat(row["effective_to"]) if row["effective_to"] else None,
        trading_lot=int(row["trading_lot"]),
        tick_size=Decimal(row["tick_size"]),
        price_limit_rule=cast("PriceLimitRule", price_limit_rule),
        price_limit_percent=(Decimal(row["price_limit_percent"]) if row["price_limit_percent"] else None),
        sell_availability_rule=cast("SellAvailabilityRule", row["sell_availability_rule"]),
        security_settlement_open_dates=int(row["security_settlement_open_dates"]),
        cash_settlement_open_dates=int(row["cash_settlement_open_dates"]),
        permitted_session_types=_session_types(row["permitted_session_types"]),
    )


def _session_types(value: str) -> tuple[Literal["regular", "non_regular"], ...]:
    return tuple(cast("SessionKind", session_type) for session_type in value.split("|") if session_type)
