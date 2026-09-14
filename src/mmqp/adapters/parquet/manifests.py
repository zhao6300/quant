from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


@dataclass(frozen=True, slots=True)
class ParquetManifest:
    content_id: str
    schema_id: str
    row_count: int
    checksum: str
    artifact_path: Path


def content_manifest(table: pa.Table, content_id: str, artifact_path: Path) -> ParquetManifest:
    schema_id = f"{content_id[:2]}-{len(table.schema)}"
    return ParquetManifest(
        content_id=content_id,
        schema_id=schema_id,
        row_count=table.num_rows,
        checksum=_checksum(table),
        artifact_path=artifact_path,
    )


def manifest_json(manifest: ParquetManifest) -> str:
    return json.dumps(
        {
            "content_id": manifest.content_id,
            "schema_id": manifest.schema_id,
            "row_count": manifest.row_count,
            "checksum": manifest.checksum,
            "artifact_path": str(manifest.artifact_path),
        },
        sort_keys=True,
    )


def _checksum(table: pa.Table) -> str:
    rendered = [str(row) for row in table]
    return hashlib.sha256("\n".join(rendered).encode("utf-8")).hexdigest()


def _as_json(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _as_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_as_json(item) for item in value]
    return value


def read_manifest(path: Path) -> dict[str, object]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return {
        "content_id": str(manifest["content_id"]),
        "schema_id": str(manifest["schema_id"]),
        "row_count": int(manifest["row_count"]),
        "checksum": str(manifest["checksum"]),
        "artifact_path": Path(str(manifest["artifact_path"])).as_posix(),
    }


def read_table(path: Path) -> pa.Table:
    return pq.read_table(path)
