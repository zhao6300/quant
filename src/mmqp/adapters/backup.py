from mmqp.domain.backup import BackupError


def needs_rollback(manifest_id: str, includes_credentials: bool) -> bool:
    if includes_credentials:
        if not manifest_id:
            return True
        raise BackupError(("credentials",))
    return not manifest_id
