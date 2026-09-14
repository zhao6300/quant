import fcntl
import hashlib
import os
import shutil
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

from mmqp.domain.errors import DomainError, ProblemV1
from mmqp.domain.workspace import WorkspaceRecord


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceStagedObject:
    kind: str
    schema_id: str
    schema_version: int
    record_count: int
    content: bytes
    content_hash: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceOperationRecovery:
    operation_id: str
    operation_kind: str
    recovery_status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceUnitOfWorkResult:
    operation_id: str
    workspace_id: str
    object_ids: tuple[str, ...]


class WorkspaceUnitOfWork:
    """A workspace-scoped transaction combining a file lock and SQLite."""

    def __init__(self, workspace_record: WorkspaceRecord):
        self._workspace_record = workspace_record
        self._workspace_path = Path(str(workspace_record.path))
        self._control_path = self._workspace_path / "control.sqlite3"
        self._staging_path = self._workspace_path / "staging"
        self._objects_path = self._workspace_path / "objects" / "sha256"
        self._lock_path = self._workspace_path / "locks" / "workspace.lock"
        self._lock_handle: IO[str] | None = None
        self._connection: sqlite3.Connection | None = None
        self._operation_id = uuid.uuid4().hex
        self._operation_kind = ""
        self._staged: dict[str, WorkspaceStagedObject] = {}
        self._published: dict[str, Path] = {}
        self._created_target: set[str] = set()
        self._intent_hash = ""

    def begin(self, operation_kind: str) -> WorkspaceUnitOfWorkResult | None:
        self._verify_uid()
        self._workspace_path.mkdir(parents=True, exist_ok=True)
        self._control_path.parent.mkdir(parents=True, exist_ok=True)
        self._staging_path.mkdir(parents=True, exist_ok=True)
        self._objects_path.mkdir(parents=True, exist_ok=True)
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        if self._lock_handle is None:
            self._lock_handle = self._lock_path.open("a")
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX)
        if self._connection is None:
            self._connection = sqlite3.connect(self._control_path, timeout=5, isolation_level=None)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._create_schema()
            self._connection.execute("BEGIN IMMEDIATE")
        self._operation_kind = operation_kind
        self._intent_hash = hashlib.sha256(operation_kind.encode("utf-8")).hexdigest()
        self._require_operation()
        return None

    def stage(
        self,
        *,
        kind: str,
        schema_id: str,
        schema_version: int,
        record_count: int,
        content: bytes,
    ) -> str:
        content_hash = hashlib.sha256(content).hexdigest()
        suffix = ".parquet" if "parquet" in schema_id.casefold() else ".bin"
        staged_path = self._staging_path / self._operation_id / f"{content_hash}{suffix}"
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path.write_bytes(content)
        _fsync_path(staged_path)
        _fsync_directory(staged_path.parent)
        if content_hash in self._staged:
            _ensure_unchanged(staged_path, content)
            return content_hash
        self._staged[content_hash] = WorkspaceStagedObject(
            kind=kind,
            schema_id=schema_id,
            schema_version=schema_version,
            record_count=record_count,
            content=content,
            content_hash=content_hash,
        )
        return content_hash

    def commit(self) -> WorkspaceUnitOfWorkResult:
        if self._connection is None:
            raise DomainError(
                ProblemV1(
                    kind="workspace/transaction-missing",
                    title="Workspace transaction missing",
                    status=400,
                    detail="workspace unit-of-work session is not started",
                )
            )
        object_ids: list[str] = []
        for content_hash, staged in self._staged.items():
            suffix = ".parquet" if "parquet" in staged.schema_id.casefold() else ".bin"
            target = self._objects_path / content_hash[:2] / f"{content_hash}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            _ensure_object_target(self._objects_path, target)
            if not target.is_file():
                self._created_target.add(content_hash)
            if not target.exists():
                _write_atomic(target, staged.content)
                self._published[content_hash] = target
            else:
                _ensure_unchanged(target, staged.content)
                self._published[content_hash] = target
            relative_path = target.relative_to(self._workspace_path).as_posix()
            created_at = datetime.now(UTC).isoformat()
            self._connection.execute(
                """INSERT OR IGNORE INTO workspace_objects
                    (object_id, workspace_id, kind, schema_id, schema_version, record_count,
                     content_hash, path, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    content_hash,
                    self._workspace_record.id,
                    staged.kind,
                    staged.schema_id,
                    staged.schema_version,
                    staged.record_count,
                    staged.content_hash,
                    relative_path,
                    created_at,
                ),
            )
            self._connection.execute(
                """INSERT OR IGNORE INTO workspace_object_links
                    (operation_id, workspace_id, object_id)
                   VALUES (?, ?, ?)""",
                (self._operation_id, self._workspace_record.id, content_hash),
            )
            object_ids.append(content_hash)
        self._connection.execute(
            "UPDATE workspace_operations SET intent_hash = ?, completed_at = ?, status = 'committed' WHERE operation_id = ?",
            (self._intent_hash, datetime.now(UTC).isoformat(), self._operation_id),
        )
        self._connection.commit()
        self.close()
        return WorkspaceUnitOfWorkResult(
            operation_id=self._operation_id,
            workspace_id=self._workspace_record.id,
            object_ids=tuple(object_ids),
        )

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._lock_handle is not None:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
            self._lock_handle.close()
            self._lock_handle = None

    def _cleanup(self) -> None:
        for content_hash, target in self._published.items():
            if content_hash in self._staged:
                target.unlink(missing_ok=True)

    def rollback(self) -> None:
        staging_directory = self._staging_path / self._operation_id
        if self._connection is not None:
            self._connection.rollback()
            self.close()
            try:
                self._cleanup()
            finally:
                self._published = {}
                self._created_target = set()
        else:
            for content_hash in self._staged:
                if content_hash not in self._created_target:
                    suffix = (
                        ".parquet"
                        if self._staged[content_hash].schema_id.casefold().find("parquet") != -1
                        else ".bin"
                    )
                    target = self._objects_path / content_hash[:2] / f"{content_hash}{suffix}"
                    target.unlink(missing_ok=True)
        if staging_directory.exists():
            shutil.rmtree(staging_directory)
        self._staged = {}

    def execute(
        self,
        callback: Callable[[WorkspaceStagedObject], Any] | None = None,
    ) -> WorkspaceUnitOfWorkResult:
        self.begin("manual")
        try:
            if callback is not None and self._staged:
                callback(next(iter(self._staged.values())))
        except BaseException:
            self.rollback()
            raise
        return self.commit()

    def _verify_uid(self) -> None:
        if self._workspace_record.bound_uid != os.geteuid():
            raise DomainError(
                ProblemV1(
                    kind="workspace/identity-mismatch",
                    title="Workspace identity mismatch",
                    status=403,
                    detail="current uid does not match bound uid",
                )
            )

    def _require_operation(self) -> None:
        if self._connection is None:
            raise DomainError(
                ProblemV1(
                    kind="workspace/transaction-missing",
                    title="Workspace transaction missing",
                    status=400,
                    detail="workspace unit-of-work session is not started",
                )
            )
        existing = self._connection.execute(
            "SELECT operation_id FROM workspace_operations WHERE operation_id = ?",
            (self._operation_id,),
        ).fetchone()
        if existing is not None:
            raise DomainError(
                ProblemV1(
                    kind="workspace/operation-duplicate",
                    title="Workspace operation duplicate",
                    status=409,
                    detail=f"operation_id {self._operation_id} already exists",
                )
            )
        self._connection.execute(
            "INSERT INTO workspace_operations(operation_id, workspace_id, kind, intent_hash, started_at, status) VALUES (?, ?, ?, ?, ?, 'started')",
            (
                self._operation_id,
                self._workspace_record.id,
                self._operation_kind,
                self._intent_hash,
                datetime.now(UTC).isoformat(),
            ),
        )

    def _create_schema(self) -> None:
        if self._connection is None:
            raise DomainError(
                ProblemV1(
                    kind="workspace/transaction-missing",
                    title="Workspace transaction missing",
                    status=400,
                    detail="workspace unit-of-work session is not started",
                )
            )
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspace_operations (
                operation_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                intent_hash TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workspace_objects (
                object_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                schema_id TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                record_count INTEGER NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS workspace_object_links (
                operation_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                object_id TEXT NOT NULL,
                PRIMARY KEY(operation_id, object_id),
                FOREIGN KEY(operation_id) REFERENCES workspace_operations(operation_id),
                FOREIGN KEY(object_id) REFERENCES workspace_objects(object_id)
            );
            CREATE TRIGGER IF NOT EXISTS workspace_objects_immutable_update
                BEFORE UPDATE ON workspace_objects
            BEGIN
                SELECT RAISE(ABORT, 'workspace objects are immutable');
            END;
            CREATE TRIGGER IF NOT EXISTS workspace_objects_immutable_delete
                BEFORE DELETE ON workspace_objects
            BEGIN
                SELECT RAISE(ABORT, 'workspace objects are immutable');
            END;
            CREATE TRIGGER IF NOT EXISTS workspace_operations_immutable_update
                BEFORE UPDATE OF workspace_id, kind, started_at ON workspace_operations
            BEGIN
                SELECT RAISE(ABORT, 'workspace operations are immutable');
            END;
            """
        )


def _ensure_unchanged(path: Path, content: bytes) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"workspace staged object is missing: {path}")
    if path.read_bytes() != content:
        raise FileExistsError(f"workspace object hash conflict: {path}")


def _fsync_path(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_object_target(root: Path, path: Path) -> None:
    root_candidate = root.resolve(strict=False)
    target = path.resolve(strict=False)
    if root_candidate not in target.parents:
        raise DomainError(
            ProblemV1(
                kind="workspace/object-path-invalid",
                title="Workspace object path is invalid",
                status=500,
                detail="object target escapes workspace objects directory",
            )
        )
    if target.is_symlink():
        raise DomainError(
            ProblemV1(
                kind="workspace/object-symlink",
                title="Workspace object symlink",
                status=409,
                detail="object paths cannot be symlinks",
            )
        )


def _write_atomic(path: Path, content: bytes) -> None:
    temporary = path.with_name(f"{path.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_bytes(content)
    _fsync_path(temporary)
    os.replace(temporary, path)
    _fsync_directory(path.parent)
