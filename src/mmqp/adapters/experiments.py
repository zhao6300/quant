from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from mmqp.domain.experiments import Artifact, Manifest


class ManifestBuilder:
    def __init__(self, source: Manifest) -> None:
        self._source = source

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> ManifestBuilder:
        return cls(
            Manifest(
                tuple(values),
                tuple(
                    Artifact(str(value), str(value))
                    for value in values.values()
                    for value in (value,)
                ),
                str(values),
            )
        )

    def preview(self, query: Sequence[str]) -> tuple[str, ...]:
        return tuple(query)
