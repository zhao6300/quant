from mmqp.domain.backup import BackupError


def pre_restore_check(free_bytes: int, estimate: int) -> bool:
    if free_bytes < estimate:
        raise BackupError(("provider",))
    return True
