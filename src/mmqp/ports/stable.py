from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceRefV1:
    workspace_id: str
    path: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateWorkspaceV1:
    path: str
    display_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MutationIntentV1:
    operation_id: str
    workspace_id: str
    command: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ContentObjectV1:
    content_id: str
    path: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactRefV1:
    kind: str
    version_id: str
    content_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DataSnapshotV1:
    snapshot_id: str
    artifacts: tuple[ArtifactRefV1, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifiedSnapshotV1:
    snapshot: DataSnapshotV1


@dataclass(frozen=True, slots=True, kw_only=True)
class TypedQueryV1:
    dataset: str
    snapshot_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ResearchRunRequestV1:
    manifest_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ResearchRunRefV1:
    run_id: str
    manifest_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RunComparisonV1:
    left_run_id: str
    right_run_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BackupManifestV1:
    backup_id: str
    manifest_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SecurityStateV1:
    endpoint: str


class WorkspacePort(Protocol):
    def create(self, request: CreateWorkspaceV1) -> WorkspaceRefV1: ...
    def open(self, workspace_id: str, path: str) -> WorkspaceRefV1: ...
    def unit_of_work(self, operation: MutationIntentV1) -> object: ...


class ContentStorePort(Protocol):
    def stage(self, content: bytes) -> ContentObjectV1: ...
    def verify(self, content_id: str) -> bool: ...
    def publish(self, content_id: str) -> ContentObjectV1: ...


class SnapshotPort(Protocol):
    def create(self, artifacts: tuple[ArtifactRefV1, ...]) -> DataSnapshotV1: ...
    def resolve(self, snapshot_id: str) -> VerifiedSnapshotV1: ...


class ResearchQueryPort(Protocol):
    def query(self, query: TypedQueryV1) -> object: ...


class ExperimentPort(Protocol):
    def submit(self, request: ResearchRunRequestV1) -> ResearchRunRefV1: ...
    def replay(self, manifest_id: str) -> ResearchRunRefV1: ...
    def compare(self, left: str, right: str) -> RunComparisonV1: ...


class BackupPort(Protocol):
    def backup(self) -> BackupManifestV1: ...
    def restore(self, backup_id: str) -> bool: ...


class SecurityPort(Protocol):
    def endpoint(self) -> SecurityStateV1: ...
    def enforce(self, state: SecurityStateV1) -> bool: ...


class ClockPort(Protocol):
    def utc_timestamp(self) -> str: ...
