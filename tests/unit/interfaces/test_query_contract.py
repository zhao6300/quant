from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from mmqp.application.queries import (
    LIVE_SNAPSHOT_ID,
    MAX_FILTERS,
    MAX_ROWS,
    SUPPORTED_QUERY_FILTERS,
    QueryFilter,
    QuerySource,
    QueryValidationError,
    ReadonlyQueryService,
    TypedQuery,
)

AVAILABLE_SNAPSHOT = "snap-2024-03-01"


class MemoryQuerySource(QuerySource):
    def __init__(self) -> None:
        super().__init__([AVAILABLE_SNAPSHOT, LIVE_SNAPSHOT_ID])
        self.records_by_dataset: dict[str, tuple[Mapping[str, Any], ...]] = {
            "DAILY_BAR": (
                {
                    "canonical_asset_id": "B",
                    "observation_date": date(2024, 1, 2),
                    "version_id": "daily-v-b",
                    "snapshot_id": AVAILABLE_SNAPSHOT,
                    "data_provenance": "provider-1",
                    "data_quality_status": "VALID",
                    "trading_currency": "JPY",
                },
                {
                    "canonical_asset_id": "B",
                    "observation_date": date(2024, 1, 2),
                    "version_id": "daily-v-a",
                    "snapshot_id": AVAILABLE_SNAPSHOT,
                    "trading_currency": "JPY",
                },
                {
                    "canonical_asset_id": "A",
                    "observation_date": None,
                    "version_id": None,
                    "snapshot_id": AVAILABLE_SNAPSHOT,
                    "trading_currency": "USD",
                },
            ),
            "FUNDAMENTAL_FACT": (
                {
                    "canonical_asset_id": "A",
                    "observation_date": date(2024, 1, 3),
                    "version_id": "fact-v-a",
                    "snapshot_id": AVAILABLE_SNAPSHOT,
                },
            ),
        }

    def records(self, snapshot_id: str, dataset: str) -> tuple[Mapping[str, Any], ...]:
        del snapshot_id
        return self.records_by_dataset[dataset]


def service(source: QuerySource | None = None) -> ReadonlyQueryService:
    return ReadonlyQueryService(source or MemoryQuerySource(), SUPPORTED_QUERY_FILTERS)


def test_query_filters_applied_sorted_null_first_and_read_only() -> None:
    source = MemoryQuerySource()
    records = list(source.records(AVAILABLE_SNAPSHOT, "DAILY_BAR"))
    result = service(source).query(TypedQuery(AVAILABLE_SNAPSHOT, "DAILY_BAR", ()))
    assert [row["version_id"] for row in result.rows] == [None, "daily-v-a", "daily-v-b"]
    assert [row["canonical_asset_id"] for row in result.rows] == ["A", "B", "B"]
    assert result.matching_count == 3
    assert result.returned_count == 3
    assert result.applied_filter_count == 0
    assert result.additional_results is False
    assert result.query == {"dataset": "DAILY_BAR", "filters": [], "limit": 100, "offset": 0}
    assert list(source.records(AVAILABLE_SNAPSHOT, "DAILY_BAR")) == records


def test_query_matches_multiple_values_and_summary() -> None:
    source = MemoryQuerySource()
    result = service(source).query(
        TypedQuery(
            AVAILABLE_SNAPSHOT,
            "DAILY_BAR",
            (QueryFilter("trading_currency", ("USD", "JPY")),),
        )
    )
    assert result.matching_count == 3
    assert result.applied_filter_count == 1


def test_query_rejects_unavailable_snapshot_and_unsupported_fields() -> None:
    with pytest.raises(QueryValidationError) as unavailable:
        service().query(TypedQuery("missing", "DAILY_BAR", ()))
    assert unavailable.value.error_codes == ["snapshot.unavailable"]

    with pytest.raises(QueryValidationError) as unsupported:
        service().query(
            TypedQuery(
                AVAILABLE_SNAPSHOT,
                "DAILY_BAR",
                (QueryFilter("unsupported", ("A",)),),
            )
        )
    assert unsupported.value.error_codes == ["filter.unsupported"]
    assert unsupported.value.fields == ["filters[1].field"]


def test_query_rejects_more_than_twenty_filters() -> None:
    filters = tuple(QueryFilter("provider", ("provider-1",)) for _ in range(MAX_FILTERS + 1))
    with pytest.raises(QueryValidationError) as error:
        service().query(TypedQuery(AVAILABLE_SNAPSHOT, "DAILY_BAR", filters))
    assert error.value.error_codes == ["filters.limit"]


def test_query_limits_to_ten_thousand() -> None:
    class LargeQuerySource(MemoryQuerySource):
        def records(self, snapshot_id: str, dataset: str) -> tuple[Mapping[str, Any], ...]:
            del snapshot_id, dataset
            return tuple(
                {
                    "canonical_asset_id": f"{position:05}",
                    "observation_date": date(2024, 1, 1),
                    "version_id": f"v-{position:05}",
                    "snapshot_id": AVAILABLE_SNAPSHOT,
                }
                for position in range(MAX_ROWS + 1)
            )

    result = service(LargeQuerySource()).query(
        TypedQuery(AVAILABLE_SNAPSHOT, "DAILY_BAR", (), limit=MAX_ROWS)
    )
    assert result.matching_count == MAX_ROWS + 1
    assert result.returned_count == MAX_ROWS
    assert result.additional_results is True


def test_query_paginates_with_explicit_offset_and_limit() -> None:
    class PaginatedSource(QuerySource):
        def __init__(self) -> None:
            super().__init__([AVAILABLE_SNAPSHOT])

        def records(self, snapshot_id: str, dataset: str) -> tuple[Mapping[str, Any], ...]:
            del snapshot_id, dataset
            return tuple(
                {
                    "canonical_asset_id": f"{position:02}",
                    "observation_date": date(2024, 1, 1),
                    "version_id": f"v-{position:02}",
                    "snapshot_id": AVAILABLE_SNAPSHOT,
                }
                for position in range(3)
            )

    result = service(PaginatedSource()).query(
        TypedQuery(AVAILABLE_SNAPSHOT, "DAILY_BAR", (), limit=1, offset=1)
    )
    assert result.query == {
        "dataset": "DAILY_BAR",
        "filters": [],
        "limit": 1,
        "offset": 1,
    }
    assert result.matching_count == 3
    assert result.returned_count == 1
    assert [row["version_id"] for row in result.rows] == ["v-01"]
    assert result.additional_results is True


def test_query_rejects_out_of_range_pagination() -> None:
    with pytest.raises(QueryValidationError) as error:
        service().query(
            TypedQuery(
                AVAILABLE_SNAPSHOT,
                "DAILY_BAR",
                (),
                limit=MAX_ROWS + 1,
                offset=-1,
            )
        )
    assert error.value.error_codes == ["limit.range", "offset.range"]
    assert set(error.value.fields) == {"limit", "offset"}


def test_repository_backed_source_supports_live_dataset() -> None:
    assert LIVE_SNAPSHOT_ID == "LIVE"
    assert set(SUPPORTED_QUERY_FILTERS["DAILY_BAR"]) >= {"canonical_asset_id", "provider"}


def test_filter_values_are_typed() -> None:
    values = (Decimal("1.20"), date(2024, 1, 1), datetime.now(), None)
    filter_ = QueryFilter("provider", values)
    assert filter_.values[0] == Decimal("1.20")


def test_query_control_plane_records_sort_null_first() -> None:
    class ControlPlaneSource(QuerySource):
        def __init__(self) -> None:
            super().__init__([AVAILABLE_SNAPSHOT])

        def records(self, snapshot_id: str, dataset: str) -> tuple[Mapping[str, Any], ...]:
            del snapshot_id, dataset
            return (
                {
                    "canonical_asset_id": "US",
                    "observation_date": date(2024, 1, 2),
                    "version_id": "v-us",
                },
                {
                    "canonical_asset_id": None,
                    "observation_date": date(2024, 1, 1),
                    "version_id": "v-null",
                    "timezone": "UTC",
                },
            )

    result = service(ControlPlaneSource()).query(
        TypedQuery(
            AVAILABLE_SNAPSHOT,
            "TRADING_CALENDAR",
            (),
        )
    )
    assert [row["version_id"] for row in result.rows] == ["v-null", "v-us"]
