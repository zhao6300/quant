from collections.abc import Mapping

from mmqp.domain.backup import DatasetManifest, verify_manifest


def verify_backup(manifest: DatasetManifest, source: Mapping[str, list[str]]) -> tuple[str, ...]:
    verify_manifest(manifest, source)
    return tuple(source)
