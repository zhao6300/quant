from __future__ import annotations

from builtins import list as list_type
from datetime import date
from pathlib import Path
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq

from mmqp.domain.errors import DomainError, ProblemV1
from mmqp.domain.universes import (
    UniverseMembership,
    membership_content_id,
)


class ParquetUniverseMembershipRepository:
    """Content-addressed immutable Parquet projection of universe membership."""

    def __init__(self, root_path: str | Path):
        self._root_path = Path(root_path)

    def create(self, membership: UniverseMembership) -> UniverseMembership:
        content_id = membership_content_id(membership)
        digest = content_id.removeprefix("sha256:")
        storage_path = self._root_path / "objects" / digest[:2] / f"{digest}.parquet"
        if storage_path.exists():
            existing_content = _rows_from_table(pq.read_table(storage_path))[0]
            if existing_content["membership_id"] != membership.membership_id:
                raise DomainError(
                    ProblemV1(
                        kind="universe/membership-content-conflict",
                        title="Universe membership content conflict",
                        status=409,
                        detail=f"content id {content_id} already exists",
                    )
                )
            if existing_content["membership_id"] == membership.membership_id:
                raise DomainError(
                    ProblemV1(
                        kind="universe/membership-conflict",
                        title="Universe membership conflict",
                        status=409,
                        detail=f"universe membership {membership.membership_id} already exists",
                    )
                )
            return membership

        staging_path = self._root_path / "staging" / f"{digest}.parquet"
        staging_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "membership_id": membership.membership_id,
                "universe_version": membership.universe_version,
                "canonical_asset_id": membership.canonical_asset_id,
                "effective_from": membership.effective_from,
                "effective_to": membership.effective_to,
                "membership_source": membership.membership_source,
                "source_version": membership.source_version,
                "content_id": content_id,
            }
        ]
        table = pa.Table.from_pylist(rows, schema=_membership_schema())
        metadata = {
            b"schema_version": b"universe.membership.v1",
            b"content_id": content_id.encode("ascii"),
        }
        table = table.replace_schema_metadata(metadata)
        pq.write_table(table, staging_path)
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        staging_path.replace(storage_path)
        return membership

    def list(self) -> list_type[UniverseMembership]:
        object_root = self._root_path / "objects"
        if not object_root.exists():
            return []
        memberships = [
            _membership_from_file(membership_path) for membership_path in object_root.glob("**/*.parquet")
        ]
        memberships.sort(
            key=lambda membership: (
                membership.effective_from,
                membership.canonical_asset_id,
                membership.membership_id,
            )
        )
        return memberships

    def find(self, membership_id: str) -> UniverseMembership | None:
        return next(
            (membership for membership in self.list() if membership.membership_id == membership_id), None
        )

    def close(self) -> None:
        return None


def _membership_schema() -> pa.Schema:
    return pa.schema(
        [
            ("membership_id", pa.string()),
            ("universe_version", pa.string()),
            ("canonical_asset_id", pa.string()),
            ("effective_from", pa.date32()),
            ("effective_to", pa.date32()),
            ("membership_source", pa.string()),
            ("source_version", pa.string()),
            ("content_id", pa.string()),
        ]
    )


def _rows_from_table(table: pa.Table) -> list[dict[str, date | str | None]]:
    rows = table.to_pylist()
    return cast(list[dict[str, date | str | None]], rows)


def _membership_from_file(membership_path: Path) -> UniverseMembership:
    row = _rows_from_table(pq.read_table(membership_path))[0]
    return UniverseMembership(
        membership_id=cast(str, row["membership_id"]),
        universe_version=cast(str, row["universe_version"]),
        canonical_asset_id=cast(str, row["canonical_asset_id"]),
        effective_from=date.fromisoformat(str(row["effective_from"])),
        effective_to=date.fromisoformat(str(row["effective_to"]))
        if row["effective_to"] is not None
        else None,
        membership_source=cast(str, row["membership_source"]),
        source_version=cast(str, row["source_version"]),
    )
