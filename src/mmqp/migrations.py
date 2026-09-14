from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MigrationReport:
    backup: Path
    free_bytes: int
    target_bytes: int
    pre_restore: bool
    post_restore: bool
