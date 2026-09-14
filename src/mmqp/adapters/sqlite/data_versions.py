import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal

from mmqp.domain.errors import DomainError, ProblemV1
from mmqp.domain.ingestion import (
    DailyBar,
    DatasetType,
    DataVersion,
    FactExclusion,
    FactSelection,
    FundamentalFact,
    FundNav,
    canonical_content_id,
)


class SqliteDataVersionRepository:
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
        pass

    def publish(self, observation: DailyBar | FundNav | FundamentalFact) -> DataVersion:
        dataset = dataset_for(observation)
        logical_date = logical_date_for(observation)
        logical_key = logical_key_for(observation)
        content_id = canonical_content_id(observation)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT v.* FROM current_data_versions c
                JOIN data_versions v ON v.version_id = c.current_version_id
                WHERE c.dataset = ? AND c.logical_key = ?
                """,
                (dataset, logical_key),
            ).fetchone()
            if row is not None and row["content_id"] == content_id:
                return _data_version(row)
            predecessor_id = None if row is None else row["version_id"]
            revision_position = 1 if row is None else row["revision_position"] + 1
            revision_id = _revision_id(dataset, logical_key, predecessor_id, content_id)
            version_id = _version_id(revision_id, content_id)
            created_at = datetime.now(UTC).isoformat()
            connection.execute(
                """
                INSERT INTO data_versions
                    (version_id, revision_id, dataset, canonical_asset_id, logical_date, logical_key,
                     predecessor_id, revision_position, created_at, content_id, observation_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    revision_id,
                    dataset,
                    observation.canonical_asset_id,
                    logical_date.isoformat(),
                    logical_key,
                    predecessor_id,
                    revision_position,
                    created_at,
                    content_id,
                    json.dumps(asdict(observation), sort_keys=True, default=_json_value),
                ),
            )
            connection.execute(
                """
                INSERT INTO current_data_versions
                    (dataset, logical_key, canonical_asset_id, logical_date, current_version_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(dataset, logical_key) DO UPDATE
                SET canonical_asset_id = excluded.canonical_asset_id,
                    logical_date = excluded.logical_date,
                    current_version_id = excluded.current_version_id
                """,
                (
                    dataset,
                    logical_key,
                    observation.canonical_asset_id,
                    logical_date.isoformat(),
                    version_id,
                ),
            )
            created = connection.execute(
                "SELECT * FROM data_versions WHERE version_id = ?",
                (version_id,),
            ).fetchone()
        return _data_version(created)

    def current_version(
        self,
        dataset: DatasetType,
        canonical_asset_id: str,
        logical_date: date,
    ) -> DataVersion | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT v.* FROM current_data_versions c
                JOIN data_versions v ON v.version_id = c.current_version_id
                WHERE c.dataset = ?
                  AND c.canonical_asset_id = ?
                  AND c.logical_date = ?
                """,
                (dataset, canonical_asset_id, logical_date.isoformat()),
            ).fetchone()
        return None if row is None else _data_version(row)

    def current_observations(self) -> list[DataVersion]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT v.* FROM current_data_versions c
                JOIN data_versions v ON v.version_id = c.current_version_id
                """,
            ).fetchall()
        return [_data_version(row) for row in rows]

    def fact_history(
        self,
        canonical_asset_id: str,
        metric_name: str,
        reporting_period_start: date,
        reporting_period_end: date,
    ) -> list[DataVersion]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM data_versions
                 WHERE dataset = 'FUNDAMENTAL_FACT'
                   AND canonical_asset_id = ?
                   AND json_extract(observation_json, '$.metric_name') = ?
                   AND json_extract(observation_json, '$.reporting_period_start') = ?
                   AND json_extract(observation_json, '$.reporting_period_end') = ?
                 ORDER BY revision_position, version_id
                """,
                (
                    canonical_asset_id,
                    metric_name,
                    reporting_period_start.isoformat(),
                    reporting_period_end.isoformat(),
                ),
            ).fetchall()
        return [_data_version(row) for row in rows]

    def select_fact(
        self,
        canonical_asset_id: str,
        metric_name: str,
        reporting_period_start: date,
        reporting_period_end: date,
        decision_at: datetime,
    ) -> FactSelection:
        if decision_at.tzinfo is None:
            raise DomainError(
                ProblemV1(
                    kind="ingestion/decision-timestamp-invalid",
                    title="Decision timestamp requires UTC offset",
                    status=422,
                    detail=decision_at.isoformat(),
                )
            )
        history = self.fact_history(
            canonical_asset_id,
            metric_name,
            reporting_period_start,
            reporting_period_end,
        )
        visible = [version for version in history if version.observation.provider_available_at <= decision_at]
        selected = max(
            visible,
            key=lambda version: (
                version.observation.provider_available_at,
                version.revision_position,
            ),
            default=None,
        )
        excluded = tuple(
            FactExclusion(
                data_version_id=version.version_id,
                content_id=version.content_id,
                revision_id=version.revision_id,
                revision_version=_observation(version).revision_version,
                available_at=_observation(version).provider_available_at,
                reason="decision-time-before-provider-available-at",
            )
            for version in history
            if _observation(version).provider_available_at > decision_at
        )
        return FactSelection(
            observation=None if selected is None else _observation(selected),
            excluded=excluded,
        )

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS data_versions (
                version_id TEXT PRIMARY KEY,
                revision_id TEXT NOT NULL,
                dataset TEXT NOT NULL CHECK (dataset IN ('DAILY_BAR','FUND_NAV','FUNDAMENTAL_FACT')),
                canonical_asset_id TEXT NOT NULL,
                logical_date TEXT NOT NULL,
                logical_key TEXT NOT NULL,
                predecessor_id TEXT,
                revision_position INTEGER NOT NULL CHECK (revision_position > 0),
                created_at TEXT NOT NULL,
                content_id TEXT NOT NULL,
                observation_json TEXT NOT NULL,
                UNIQUE (dataset, logical_key, revision_id),
                UNIQUE (dataset, logical_key, content_id),
                UNIQUE (dataset, canonical_asset_id, content_id),
                FOREIGN KEY (predecessor_id) REFERENCES data_versions(version_id)
            );
            CREATE TABLE IF NOT EXISTS current_data_versions (
                dataset TEXT NOT NULL CHECK (dataset IN ('DAILY_BAR','FUND_NAV','FUNDAMENTAL_FACT')),
                logical_key TEXT NOT NULL,
                canonical_asset_id TEXT NOT NULL,
                logical_date TEXT NOT NULL,
                current_version_id TEXT NOT NULL,
                PRIMARY KEY (dataset, logical_key),
                FOREIGN KEY (current_version_id) REFERENCES data_versions(version_id)
            );
            CREATE INDEX IF NOT EXISTS data_versions_history
                ON data_versions(dataset, canonical_asset_id, logical_date, revision_position DESC);
            CREATE INDEX IF NOT EXISTS data_versions_content_id ON data_versions(content_id);
            CREATE INDEX IF NOT EXISTS current_data_versions_lookup
                ON current_data_versions(canonical_asset_id, logical_date);
            CREATE TRIGGER IF NOT EXISTS data_versions_immutable_update
                BEFORE UPDATE OF version_id, revision_id, dataset, canonical_asset_id, logical_date,
                    logical_key, predecessor_id, revision_position, created_at, content_id, observation_json
                ON data_versions
            BEGIN
                SELECT RAISE(ABORT, 'data_versions is immutable');
            END;
            CREATE TRIGGER IF NOT EXISTS data_versions_immutable_delete
                BEFORE DELETE ON data_versions
            BEGIN
                SELECT RAISE(ABORT, 'data_versions is immutable');
            END;
            """
        )


def dataset_for(observation: DailyBar | FundNav | FundamentalFact) -> DatasetType:
    if isinstance(observation, DailyBar):
        return "DAILY_BAR"
    if isinstance(observation, FundNav):
        return "FUND_NAV"
    return "FUNDAMENTAL_FACT"


def logical_date_for(observation: DailyBar | FundNav | FundamentalFact) -> date:
    if isinstance(observation, DailyBar):
        return observation.trading_date
    if isinstance(observation, FundNav):
        return observation.valuation_date
    return observation.reporting_period_end


def logical_key_for(observation: DailyBar | FundNav | FundamentalFact) -> str:
    if isinstance(observation, DailyBar):
        return f"{observation.canonical_asset_id}|{observation.trading_date.isoformat()}"
    if isinstance(observation, FundNav):
        return f"{observation.canonical_asset_id}|{observation.valuation_date.isoformat()}"
    return (
        f"{observation.canonical_asset_id}|{observation.metric_name}|"
        f"{observation.reporting_period_start.isoformat()}|{observation.reporting_period_end.isoformat()}"
    )


def _observation(version: DataVersion) -> FundamentalFact:
    if not isinstance(version.observation, FundamentalFact):
        raise DomainError(
            ProblemV1(
                kind="ingestion/repository-integrity-invalid",
                title="Fundamental fact version contains another dataset",
                status=500,
                detail=version.version_id,
            )
        )
    return version.observation


def _data_version(row: sqlite3.Row) -> DataVersion:
    observation_json = json.loads(row["observation_json"])
    observation: DailyBar | FundNav | FundamentalFact
    if row["dataset"] == "DAILY_BAR":
        observation = _daily_bar(_object_values(observation_json))
    elif row["dataset"] == "FUND_NAV":
        observation = _fund_nav(_object_values(observation_json))
    else:
        observation = _fact(_object_values(observation_json))
    return DataVersion(
        version_id=row["version_id"],
        revision_id=row["revision_id"],
        dataset=row["dataset"],
        canonical_asset_id=row["canonical_asset_id"],
        logical_date=date.fromisoformat(row["logical_date"]),
        logical_key=row["logical_key"],
        predecessor_id=row["predecessor_id"],
        revision_position=row["revision_position"],
        created_at=datetime.fromisoformat(row["created_at"]),
        content_id=row["content_id"],
        observation=observation,
    )


def _object_values(raw_values: object) -> dict[str, object]:
    return raw_values if isinstance(raw_values, dict) else {}


def _daily_bar(values: dict[str, object]) -> DailyBar:
    return DailyBar(
        canonical_asset_id=str(values["canonical_asset_id"]),
        trading_date=date.fromisoformat(str(values["trading_date"])),
        open=Decimal(str(values["open"])),
        high=Decimal(str(values["high"])),
        low=Decimal(str(values["low"])),
        close=Decimal(str(values["close"])),
        volume=Decimal(str(values["volume"])),
        turnover=Decimal(str(values["turnover"])),
        trading_currency=str(values["trading_currency"]),
        provider_available_at=datetime.fromisoformat(str(values["provider_available_at"])),
        retrieved_at=datetime.fromisoformat(str(values["retrieved_at"])),
        provider=str(values["provider"]),
        provider_code=str(values["provider_code"]),
        provenance_id=str(values["provenance_id"]),
    )


def _fund_nav(values: dict[str, object]) -> FundNav:
    return FundNav(
        canonical_asset_id=str(values["canonical_asset_id"]),
        valuation_date=date.fromisoformat(str(values["valuation_date"])),
        unit_nav=Decimal(str(values["unit_nav"])),
        cumulative_nav=None if values["cumulative_nav"] is None else Decimal(str(values["cumulative_nav"])),
        pricing_currency=str(values["pricing_currency"]),
        provider_available_at=datetime.fromisoformat(str(values["provider_available_at"])),
        retrieved_at=datetime.fromisoformat(str(values["retrieved_at"])),
        provider=str(values["provider"]),
        provider_code=str(values["provider_code"]),
        provenance_id=str(values["provenance_id"]),
    )


def _fact(values: dict[str, object]) -> FundamentalFact:
    return FundamentalFact(
        canonical_asset_id=str(values["canonical_asset_id"]),
        metric_name=str(values["metric_name"]),
        value=Decimal(str(values["value"])),
        unit=str(values["unit"]),
        currency=None if values["currency"] is None else str(values["currency"]),
        reporting_period_start=date.fromisoformat(str(values["reporting_period_start"])),
        reporting_period_end=date.fromisoformat(str(values["reporting_period_end"])),
        announcement_at=datetime.fromisoformat(str(values["announcement_at"])),
        provider_available_at=datetime.fromisoformat(str(values["provider_available_at"])),
        provider=str(values["provider"]),
        revision_version=str(values["revision_version"]),
        provenance_id=str(values["provenance_id"]),
    )


def _revision_id(
    dataset: str,
    logical_key: str,
    predecessor_id: str | None,
    content_id: str,
) -> str:
    payload = "\x1f".join(
        ("" if predecessor_id is None else predecessor_id, dataset, logical_key, content_id)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _version_id(revision_id: str, content_id: str) -> str:
    return hashlib.sha256(f"{revision_id}\x1f{content_id}".encode()).hexdigest()


def _json_value(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:f}"
    if isinstance(value, (DailyBar, FundNav, FundamentalFact)):
        raise TypeError("DataVersion cannot be embedded")
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")
