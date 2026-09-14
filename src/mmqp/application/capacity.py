from mmqp.domain.backup import BackupError


def check_backup_gate(free_bytes: int, estimate: int) -> tuple[int, int]:
    if free_bytes < estimate:
        raise BackupError(("provider",))
    return free_bytes, estimate
