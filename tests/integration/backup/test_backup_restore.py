from __future__ import annotations

from mmqp.application.backup import verify_backup
from mmqp.domain.backup import dataset_manifest


def test_backup_unit_restore_placeholder():
    manifest = dataset_manifest("dataset", "identity", ("record-a", "record-b"), ("version-1",))
    assert verify_backup(manifest, {"record-a": ["x"], "record-b": ["x"]})
