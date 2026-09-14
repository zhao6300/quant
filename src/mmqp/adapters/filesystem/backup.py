from mmqp.application.backup import verify_backup
from mmqp.domain.backup import BackupError, DatasetManifest


def restore_backup(
    manifest: DatasetManifest,
    records: dict[str, list[str]],
    before: list[str],
) -> bool:
    try:
        if not verify_backup(manifest, records):
            return False
    except BackupError:
        return not before
    return True
