from __future__ import annotations

from pydantic import BaseModel, Field

from mmqp.application.queries import QueryFilter


class QueryFilterModel(BaseModel):
    field: str
    values: tuple[str, ...] = ()


class TypedQueryModel(BaseModel):
    snapshot_id: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    filters: tuple[QueryFilterModel, ...] = ()
    limit: int = Field(default=100, ge=1, le=10_000)
    offset: int = Field(default=0, ge=0)


class QueryRequestModel(BaseModel):
    snapshot_id: str = Field(default="LIVE", min_length=1)
    dataset: str = Field(min_length=1)
    filters: tuple[QueryFilterModel, ...] = ()


class ResearchInterface:
    def confirm_int(self, value: object) -> int:
        if not isinstance(value, int):
            raise ValueError("value must be an integer")
        return int(value)

    def select(self, frequency: str, desired_mode: str) -> str:
        frequency = frequency.casefold()
        if frequency == "daily":
            return desired_mode
        if frequency in {"weekly", "monthly"}:
            return "daily"
        raise ValueError("unsupported plan frequency")

    def find_filter(self, field: str) -> QueryFilter | None:
        if field == "canonical_asset_id":
            return QueryFilter(field=field, values=("A",))
        return None
