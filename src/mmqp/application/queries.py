from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from mmqp.domain.errors import DomainError, ProblemV1

QUERY_DATASETS: frozenset[str] = frozenset(
    {
        "ASSET_MASTER",
        "DAILY_BAR",
        "FUND_NAV",
        "FUNDAMENTAL_FACT",
        "TRADING_CALENDAR",
        "MARKET_RULE_PROFILE",
        "VALUATION_CALENDAR",
        "CORPORATE_ACTION",
    }
)
LIVE_SNAPSHOT_ID = "LIVE"
MAX_FILTERS = 20
MAX_ROWS = 10_000
SUPPORTED_QUERY_FILTERS: Mapping[str, frozenset[str]] = {
    "ASSET_MASTER": frozenset({"canonical_asset_id", "asset_type", "market", "name"}),
    "DAILY_BAR": frozenset({"canonical_asset_id", "trading_currency", "provider", "provenance_id"}),
    "FUND_NAV": frozenset({"canonical_asset_id", "pricing_currency", "provider", "provenance_id"}),
    "FUNDAMENTAL_FACT": frozenset(
        {
            "canonical_asset_id",
            "metric_name",
            "unit",
            "currency",
            "provider",
            "provenance_id",
        }
    ),
    "TRADING_CALENDAR": frozenset({"version_id", "market", "exchange", "timezone"}),
    "MARKET_RULE_PROFILE": frozenset({"version_id", "market", "exchange", "asset_type"}),
    "VALUATION_CALENDAR": frozenset({"version_id", "market", "timezone"}),
    "CORPORATE_ACTION": frozenset(
        {"version_id", "canonical_asset_id", "event_id", "action_type", "provider", "provenance_id"}
    ),
}

type FilterValue = str | int | Decimal | date | datetime | None


@dataclass(frozen=True, slots=True)
class QueryFilter:
    field: str
    values: tuple[FilterValue, ...]


@dataclass(frozen=True, slots=True)
class TypedQuery:
    snapshot_id: str
    dataset: str
    filters: tuple[QueryFilter, ...]
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True, slots=True)
class QueryResult:
    snapshot_id: str
    query: dict[str, Any]
    matching_count: int
    returned_count: int
    applied_filter_count: int
    additional_results: bool
    rows: tuple[dict[str, Any], ...]


class QueryValidationError(DomainError):
    def __init__(self, fields: list[str], error_codes: list[str] | None = None):
        super().__init__(
            ProblemV1(
                kind="interface/query-invalid",
                title="Research query is invalid",
                status=422,
                detail=", ".join(error_codes or fields),
                fields={field: [] for field in sorted(set(fields))} if fields else None,
            )
        )
        self.fields = list(dict.fromkeys(fields))
        self.error_codes = sorted(set(error_codes or fields))


class QuerySource:
    def __init__(self, available_snapshots: Sequence[str]) -> None:
        self._available_snapshots = frozenset(available_snapshots)

    def records(self, snapshot_id: str, dataset: str) -> tuple[Mapping[str, Any], ...]:
        del snapshot_id, dataset
        return ()

    @property
    def available_snapshot_ids(self) -> frozenset[str]:
        return self._available_snapshots


class ReadonlyQueryService:
    def __init__(
        self,
        source: QuerySource,
        supported_filters: Mapping[str, Collection[str]],
    ) -> None:
        self._source = source
        self._supported_filters = {
            dataset: frozenset(filters) for dataset, filters in supported_filters.items()
        }

    def query(self, request: TypedQuery) -> QueryResult:
        fields, error_codes = self._validation_errors(request)
        if fields or error_codes:
            raise QueryValidationError(fields, error_codes)
        records = self._source.records(request.snapshot_id, request.dataset)
        matching = [record for record in records if self._matches(record, request.filters)]
        matching.sort(key=self._record_sort_key)
        additional = len(matching) > request.offset + request.limit
        rows = matching[request.offset : request.offset + request.limit]
        return QueryResult(
            snapshot_id=request.snapshot_id,
            query=self._request_query(request),
            matching_count=len(matching),
            returned_count=len(rows),
            applied_filter_count=len(request.filters),
            additional_results=additional,
            rows=tuple(dict(record) for record in rows),
        )

    def _validation_errors(self, request: TypedQuery) -> tuple[list[str], list[str]]:
        fields: list[str] = []
        error_codes: list[str] = []
        if not request.snapshot_id or request.snapshot_id not in self._source.available_snapshot_ids:
            fields.append("snapshot_id")
            error_codes.append("snapshot.unavailable")
        if request.dataset not in QUERY_DATASETS:
            fields.append("dataset")
            error_codes.append("dataset.unsupported")
        if len(request.filters) > MAX_FILTERS:
            fields.append("filters")
            error_codes.append("filters.limit")
        if request.limit < 1 or request.limit > MAX_ROWS:
            fields.append("limit")
            error_codes.append("limit.range")
        if request.offset < 0:
            fields.append("offset")
            error_codes.append("offset.range")
        allowed = self._supported_filters.get(request.dataset, frozenset())
        forbidden_dataset_fields = {"snapshot_id", "provider_code"}
        allowed = frozenset(allowed) - forbidden_dataset_fields
        for position, item in enumerate(request.filters, start=1):
            if item.field not in allowed:
                fields.append(f"filters[{position}].field")
                error_codes.append("filter.unsupported")
        return fields, error_codes

    @staticmethod
    def _request_query(request: TypedQuery) -> dict[str, Any]:
        return {
            "dataset": request.dataset,
            "filters": list(request.filters),
            "limit": request.limit,
            "offset": request.offset,
        }

    @staticmethod
    def _matches(record: Mapping[str, Any], filters: tuple[QueryFilter, ...]) -> bool:
        aliases = {
            "trading_currency": ("currency",),
            "pricing_currency": ("currency",),
            "market": ("asset_type",),
        }
        return all(
            any(
                record.get(field_alias) in item.values
                for field_alias in (item.field, *aliases.get(item.field, ()))
            )
            for item in filters
        )

    @staticmethod
    def _record_sort_key(record: Mapping[str, Any]) -> tuple[Any, Any, Any]:
        return (
            _null_first(record.get("canonical_asset_id")),
            _null_first(
                record.get("observation_date")
                if record.get("observation_date") is not None
                else record.get("available_at")
            ),
            _null_first(
                record.get("version_id")
                if record.get("version_id") is not None
                else record.get("data_version_id")
            ),
        )


def _null_first(value: Any) -> tuple[int, Any]:
    if value is None:
        return 0, ""
    if isinstance(value, str):
        return 1, value
    return 1, value
