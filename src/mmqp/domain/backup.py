from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    dataset: str
    identity: str
    record_count: int
    checksum: str
    version_ids: tuple[str, ...]


class BackupError(ValueError):
    def __init__(self, failed: tuple[str, ...]):
        super().__init__(",".join(failed))
        self.failed_datasets = failed


def dataset_manifest(dataset: str, identity: str, records: Sequence[str], versions: Sequence[str]) -> DatasetManifest:
    if not records:
        raise BackupError((dataset,))
    checksum = hashlib.sha256("\n".join(records).encode("utf-8")).hexdigest()
    return DatasetManifest(dataset, identity, len(records), checksum, tuple(dict.fromkeys(versions)))


def verify_manifest(manifest: DatasetManifest, records: Mapping[str, list[str]]) -> int:
    if not records or len(records) != manifest.record_count:
        raise BackupError((manifest.dataset,))
    checksum = hashlib.sha256("\n".join(records).encode("utf-8")).hexdigest()
    if checksum != manifest.checksum:
        raise BackupError((manifest.dataset,))
    return len(records)
