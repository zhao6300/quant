from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class RaisesErrors(Protocol):
    def __enter__(self) -> object: ...

    def __exit__(self, *args: object) -> None:
        del args


def assert_raises(agent: Mapping[str, object]) -> None:
    """Report explicit errors for a portable ma source."""
    _ = agent
