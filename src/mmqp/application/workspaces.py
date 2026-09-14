import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from mmqp.domain.errors import DomainError, ProblemV1
from mmqp.domain.workspace import (
    WorkspaceConflict,
    WorkspaceConflictError,
    WorkspaceRecord,
    canonical_path_key,
    canonicalize_workspace_path,
)
from mmqp.ports.workspace_repository import WorkspaceRepository


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository):
        self._repository = repository

    def open(self, raw_path: str) -> WorkspaceRecord:
        requested = str(canonicalize_workspace_path(raw_path))
        requested_key = canonical_path_key(requested)
        record = self._repository.get_by_path(requested)
        if record is None:
            candidates = [
                candidate
                for candidate in self._repository.list()
                if canonical_path_key(candidate.path) == requested_key
            ]
            if len(candidates) == 1:
                record = candidates[0]
        if record is None:
            raise WorkspaceConflictError(
                [
                    WorkspaceConflict(
                        conflict_kind="not-found",
                        workspace_id="",
                        path=requested,
                    )
                ],
                status=404,
                title="Workspace not found",
            )
        if record.bound_uid != os.geteuid():
            raise WorkspaceConflictError(
                [
                    WorkspaceConflict(
                        conflict_kind="identity",
                        workspace_id=record.id,
                        path=record.path,
                    )
                ],
                status=403,
                title="Workspace identity mismatch",
            )
        return record

    def get_by_path(self, raw_path: str) -> WorkspaceRecord:
        return self.open(raw_path)

    def _resolve_conflicts(self, requested_key: str, record_id: str) -> list[WorkspaceConflict]:
        conflicts: list[WorkspaceConflict] = []
        for record in self._repository.list():
            existing_key = canonical_path_key(record.path)
            if existing_key == requested_key:
                conflicts.append(
                    WorkspaceConflict(
                        conflict_kind="equal-path",
                        workspace_id=record.id,
                        path=record.path,
                    )
                )
            elif existing_key.startswith(requested_key + os.sep) or requested_key.startswith(
                existing_key + os.sep
            ):
                conflicts.append(
                    WorkspaceConflict(
                        conflict_kind="ancestor-or-descendant",
                        workspace_id=record.id,
                        path=record.path,
                    )
                )
            if record.id == record_id:
                conflicts.append(
                    WorkspaceConflict(
                        conflict_kind="identifier",
                        workspace_id=record.id,
                        path=record.path,
                    )
                )
        return conflicts

    def create(self, raw_path: str, display_name: str | None) -> WorkspaceRecord:
        path = canonicalize_workspace_path(raw_path)
        record = WorkspaceRecord(
            id=uuid.uuid4().hex,
            path=str(path),
            display_name=display_name or path.name,
            bound_uid=os.geteuid(),
            created_at=datetime.now(UTC),
        )
        conflicts = self._resolve_conflicts(canonical_path_key(path), record.id)
        if conflicts:
            raise WorkspaceConflictError(conflicts)
        try:
            self._materialize_workspace(path, record)
        except Exception as exc:
            raise DomainError(
                ProblemV1(
                    kind="workspace/materialization-failed",
                    title="Workspace materialization failed",
                    status=500,
                    detail=str(exc),
                )
            ) from exc
        return self._repository.create(record)

    def _materialize_workspace(self, path: Path, record: WorkspaceRecord) -> None:
        for child in ("objects", "manifests", "results", "staging", "locks", "logs", "backups"):
            (path / child).mkdir(parents=True, exist_ok=True)
        config_path = path / "workspace.toml"
        config_path.write_text(
            f"id = '{record.id}'\nuid = {record.bound_uid}\nformat_version = 1\nplatform_version = '0.1.0'\n",
            encoding="utf-8",
        )
