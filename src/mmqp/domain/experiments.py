from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Artifact:
    name: str
    content_id: str


@dataclass(frozen=True, slots=True)
class Manifest:
    runs: tuple[str, ...]
    artifacts: tuple[Artifact, ...]
    manifest_id: str


@dataclass(frozen=True, slots=True)
class RunComparison:
    alpha_weighted_return_relative_difference: Decimal
    turnover_relative_difference: Decimal


class ExperimentError(ValueError):
    pass


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


class ExperimentRunner:
    def submit(self, runs: Mapping[str, Sequence[Mapping[str, str]]], seed: int) -> Manifest:
        if not runs or not all(runs.values()):
            raise ExperimentError("experiment needs one run with data")
        return self.compose({key: tuple(value) for key, value in runs.items()}, seed)

    def compose(self, runs: Mapping[str, tuple[Mapping[str, str], ...]], seed: int) -> Manifest:
        if not runs or not all(runs.values()):
            raise ExperimentError("experiment needs one run with data")
        if seed < 0:
            raise ExperimentError("experiment seed must be non-negative")
        artifacts = tuple(
            Artifact(f"{run}:{position}", _hash(value))
            for run in sorted(runs)
            for position, value in enumerate(runs[run])
        )
        artifact_hashes = tuple((artifact.name, artifact.content_id) for artifact in artifacts)
        return Manifest(tuple(runs), artifacts, _hash((runs, seed, artifact_hashes)))

    def replay(self, manifest: Manifest, runs: Mapping[str, Sequence[Mapping[str, str]]], seed: int) -> Manifest:
        recreated = self.compose({key: tuple(value) for key, value in runs.items()}, seed)
        if recreated.manifest_id != manifest.manifest_id:
            raise ExperimentError("replay mismatch")
        return manifest


def compare_manifest(
    manifests: Sequence[str],
    alpha_metrics: Sequence[Decimal],
) -> RunComparison:
    if not manifests or not alpha_metrics:
        raise ExperimentError("run comparison needs a manifest and an alpha metric")
    if len(set(manifests)) != 1:
        raise ExperimentError("run comparison requires one manifest")
    return RunComparison(
        alpha_weighted_return_relative_difference=max(alpha_metrics) - min(alpha_metrics),
        turnover_relative_difference=Decimal("0"),
    )
