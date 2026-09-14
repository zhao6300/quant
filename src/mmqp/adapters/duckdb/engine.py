from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pyarrow as pa

from mmqp.domain.errors import DomainError, ProblemV1

_OPERATORS = {
    "=": "=",
    "==": "=",
    "!=": "!=",
    "<>": "<>",
    ">": ">",
    ">=": ">=",
    "<": "<",
    "<=": "<=",
}


def _is_identifier(identifier: str) -> bool:
    return identifier.isidentifier()


class DuckDBReadonlyEngine:
    """DuckDB engine restricted to registered snapshots and typed filters."""

    def __init__(self, views: Mapping[str, Path], limit: int = 10001):
        if limit < 1 or limit > 10001:
            raise DomainError(
                ProblemV1(
                    kind="query/limit-out-of-range",
                    title="Query limit out of range",
                    status=400,
                    detail="limit must be between 1 and 10001",
                )
            )
        self._views = dict(views)
        self._limit = limit
        self._connection = duckdb.connect(database=":memory:")
        self._connection.execute("SET threads TO 1")
        self._connection.execute("SET memory_limit TO '128MB'")
        for table_name in sorted(self._views):
            if not _is_identifier(table_name):
                raise DomainError(
                    ProblemV1(
                        kind="query/table-invalid",
                        title="Query table invalid",
                        status=400,
                        detail=f"table name {table_name} is not an identifier",
                    )
                )
        for table_name, path in self._views.items():
            self._connection.execute(
                f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet('{str(path.resolve())}')",
            )
        self._connection.execute("SET enable_external_access TO false")

    def select(
        self,
        table_name: str,
        columns: Sequence[str],
        conditions: Sequence[tuple[str, str, object]] = (),
        limit: int | None = None,
    ) -> pa.Table:
        if table_name not in self._views:
            raise DomainError(
                ProblemV1(
                    kind="query/table-unknown",
                    title="Query table unknown",
                    status=400,
                    detail=f"table {table_name} is not registered",
                )
            )
        if not columns:
            raise DomainError(
                ProblemV1(
                    kind="query/columns-empty",
                    title="Query columns empty",
                    status=400,
                    detail="columns must not be empty",
                )
            )
        if limit is None:
            limit = self._limit
        elif limit < 1 or limit > self._limit:
            raise DomainError(
                ProblemV1(
                    kind="query/limit-out-of-range",
                    title="Query limit out of range",
                    status=400,
                    detail=f"limit must be between 1 and {self._limit}",
                )
            )
        parameters: list[object] = []
        predicates: list[str] = []
        for left, operator, right in conditions:
            predicates.append(_predicate(left, operator, right, parameters))
        column_sql = ", ".join(_column_or_identifier(column) for column in columns)
        predicate_sql = f" WHERE {' AND '.join(predicates)}" if predicates else ""
        try:
            result = self._connection.execute(
                f"SELECT {column_sql} FROM {table_name}{predicate_sql} LIMIT ?",
                [*parameters, limit],
            )
        except duckdb.Error as exc:
            raise DomainError(
                ProblemV1(
                    kind="query/invalid-filter",
                    title="Query filter invalid",
                    status=400,
                    detail=str(exc),
                )
            ) from exc
        return result.to_arrow_table()


def _predicate(left: str, operator: str, right: object, parameters: list[object]) -> str:
    if not _is_identifier(left):
        raise DomainError(
            ProblemV1(
                kind="query/column-invalid",
                title="Query column invalid",
                status=400,
                detail=f"column {left} is not an identifier",
            )
        )
    if operator not in _OPERATORS:
        raise DomainError(
            ProblemV1(
                kind="query/operator-invalid",
                title="Query operator invalid",
                status=400,
                detail=f"operator {operator} is not supported",
            )
        )
    if not isinstance(right, (str, int, float, Decimal, date)):
        raise DomainError(
            ProblemV1(
                kind="query/filter-type-invalid",
                title="Query filter type invalid",
                status=400,
                detail=f"unsupported filter type {type(right).__name__}",
            )
        )
    parameters.append(right)
    return f"{left} {_OPERATORS[operator]} ?"


def _column_or_identifier(identifier: str) -> str:
    if not _is_identifier(identifier):
        raise DomainError(
            ProblemV1(
                kind="query/column-invalid",
                title="Query column invalid",
                status=400,
                detail=f"column {identifier} is not an identifier",
            )
        )
    return identifier
