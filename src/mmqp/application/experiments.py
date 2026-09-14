from __future__ import annotations

from collections.abc import Mapping

from mmqp.domain.experiments import Artifact


def accept_only_json_results(events: Mapping[str, Artifact]) -> tuple[str, ...]:
    return tuple(sorted(events))
