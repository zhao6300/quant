from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal

from mmqp.domain.errors import DomainError, ProblemV1


def typed_query(table_name: str, columns: Sequence[str], filters: Mapping[str, object]) -> str:
    conditions = []
    for left, right in filters.items():
        conditions.append(_condition(left, right))
    column_sql = ", ".join(columns)
    predicate_sql = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    return f"SELECT {column_sql} FROM {table_name}{predicate_sql}"


def _is_identifier(identifier: str) -> bool:
    return identifier.replace("_", "a").isidentifier()


def _condition(left: str, value: object) -> str:
    if isinstance(value, (str, int, float, Decimal, date)):
        return f"{left} = {_sql_literal(value)}"
    if value is None:
        return f"{left} IS NULL"
    if isinstance(value, tuple) and len(value) == 2:
        return f"{left} BETWEEN {_sql_literal(value[0])} AND {_sql_literal(value[1])}"
    raise DomainError(
        ProblemV1(
            kind="query/unsupported-filter",
            title="Unsupported filter",
            status=400,
            detail=f"unsupported value type {type(value).__name__}",
        )
    )


def _sql_literal(value: object) -> str:
    if isinstance(value, str):
        return "'" + str(value).replace("'", "''") + "'"
    return repr(value)
