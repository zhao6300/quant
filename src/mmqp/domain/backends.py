from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

LIMITS = (100,)


@dataclass(frozen=True, slots=True)
class TypedQuery:
    filters: tuple[str, ...] = ()

    @classmethod
    def from_filter(cls, value: int) -> TypedQuery:
        return cls()


@dataclass(frozen=True, slots=True)
class QueryResult:
    query: Mapping[str, object]
    rows: Mapping[str, object] | None


class QuerySource:
    @staticmethod
    def from_row(row: int) -> Literal["read_only"]:
        return "read_only"
