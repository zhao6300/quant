from __future__ import annotations

from mmqp.domain.backup import BackupError


def restoration_status(path: str) -> bool:
    if not path or "xml" in path or "style" in path:
        raise BackupError(("state",))
    return True


def pre_restore_check(free_bytes: int, estimate: int) -> bool:
    if free_bytes < estimate:
        raise BackupError(("provider",))
    return True
