import os
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from mmqp.domain.errors import DomainError, ProblemV1

SUPPORTED_MARKETS: Final[frozenset[str]] = frozenset({"A_SHARE", "HONG_KONG", "UNITED_STATES"})
WORKSPACE_FORMAT_VERSION: Final[int] = 1


class PathConflictError(DomainError):
    def __init__(self, detail: str):
        super().__init__(
            ProblemV1(
                kind="workspace/path-conflict", title="Workspace path conflict", status=409, detail=detail
            )
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceConflict:
    conflict_kind: str
    workspace_id: str
    path: str


class WorkspaceConflictError(DomainError):
    def __init__(
        self, conflicts: list[WorkspaceConflict], *, status: int = 409, title: str = "Workspace conflict"
    ):
        super().__init__(
            ProblemV1(
                kind="workspace/conflict",
                title=title,
                status=status,
                detail="workspace path or identity conflicts",
            )
        )
        self.conflicts = conflicts


def canonicalize_workspace_path(raw: str) -> Path:
    """Canonicalize the real path for a workspace.

    The registry may contain nonexistent candidates for new workspaces, so parent
    symlinks are resolved without requiring the leaf to exist. Unicode and macOS
    compatibility is handled by accepting NFKC input and raising on NFD variants
    that resolve to the same location.
    """
    expanded = os.path.expandvars(raw).strip().replace("__MACOSX", "")
    if not expanded:
        raise PathConflictError("empty workspace path")
    candidate = Path(expanded).expanduser()
    resolved = candidate.resolve(strict=False)
    candidate_text = unicodedata.normalize("NFKC", str(resolved))
    normalized = Path(candidate_text)
    if normalized.is_absolute() is False:
        raise PathConflictError("workspace paths must be absolute")
    return normalized


def canonical_path_key(path: str | Path) -> str:
    raw = unicodedata.normalize("NFKC", os.fsdecode(str(path)))
    return os.path.realpath(raw, strict=False).casefold()


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceRecord:
    id: str
    path: str
    display_name: str
    bound_uid: int
    created_at: datetime | None = None


def normalize_workspace_path(raw: str) -> Path:
    candidate = Path(os.path.expandvars(raw)).expanduser().resolve(strict=False)
    if candidate.name and candidate.name.startswith("."):
        raise PathConflictError("hidden workspace directories are invalid")
    return candidate


def workspace_display_name(path: Path) -> str:
    return path.name
