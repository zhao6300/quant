from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from mmqp.adapters.parquet.manifests import (
    ParquetManifest,
    content_manifest,
    manifest_json,
)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class ParquetContentStore:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)

    def publish(self, table: pa.Table) -> tuple[Path, ParquetManifest]:
        content_id = self.content_id(table)
        target = self.root / content_id[:2] / f"{content_id}.parquet"
        if target.exists():
            return target, content_manifest(table, content_id, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".staging")
        pq.write_table(table, temporary)
        os.replace(temporary, target)
        manifest = content_manifest(table, content_id, target)
        manifest_path = target.with_suffix(".manifest")
        manifest_path.write_text(manifest_json(manifest), encoding="utf-8")
        return target, manifest

    def content_id(self, table: pa.Table) -> str:
        buffer = pa.BufferOutputStream()
        pq.write_table(table, buffer)
        return hashlib.sha256(buffer.getvalue()).hexdigest()

    def read(self, content_id: str) -> tuple[pa.Table, ParquetManifest]:
        path = self.root / content_id[:2] / f"{content_id}.parquet"
        if not path.exists():
            raise FileNotFoundError(path)
        table = pq.read_table(path)
        manifest = content_manifest(table, content_id, path)
        return table, manifest

    def _write_atomic(self, target: Path, table: pa.Table) -> None:
        temporary = target.with_suffix(".staging.parquet")
        pq.write_table(table, temporary)
        fsync_directory(temporary.parent)
        os.replace(temporary, target)
        fsync_directory(target.parent)

    def _remove_object(self, target: Path) -> None:
        if target.parent.exists():
            shutil.rmtree(target.parent)

    def object_exists(self, content_id: str) -> bool:
        return (self.root / content_id[:2] / f"{content_id}.parquet").is_file()

    def remove(self, content_id: str) -> None:
        target = self.root / content_id[:2] / f"{content_id}.parquet"
        if target.exists():
            target.unlink()
            self._remove_object(target)

    def path(self, content_id: str) -> Path:
        return self.root / content_id[:2] / f"{content_id}.parquet"
