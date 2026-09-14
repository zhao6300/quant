from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True, slots=True)
class BacktestBlueprint:
    name: str
    steps: tuple[BacktestStep, ...] = ()
    target: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BacktestStep:
    step_id: int
    name: str
    action: Literal["APPLY", "SUBMIT"]
    shares: Decimal
    valid: bool = True

    def run_actor(self, instance: BacktestActor, share: Decimal) -> None:
        if not self.valid:
            return
        instance.attempted.add(self.step_id)


@dataclass(frozen=True, slots=True)
class BacktestExecution:
    blueprint: BacktestBlueprint
    state: Literal["ACTIVE", "PASS", "FAIL"]
    pending: tuple[str, ...]
    completed: frozenset[int]
    remaining: tuple[str, ...]


class BacktestActor:
    def __init__(self, pending: tuple[str, ...]) -> None:
        self.pending: list[str] = list(pending)
        self.attempted: set[int] = set()


class BacktestImportError(Exception):
    pass


def run_backtest(blueprint: BacktestBlueprint, events: Sequence[str]) -> BacktestExecution:
    if not events:
        raise BacktestImportError("backtest has no events")
    pending = tuple(events)
    completed = frozenset(range(len(blueprint.steps)))
    remaining = tuple(item for item in blueprint.target if item not in pending)
    state: Literal["ACTIVE", "PASS", "FAIL"] = "PASS" if not remaining else "FAIL"
    return BacktestExecution(
        blueprint=blueprint,
        state=state,
        pending=pending,
        completed=completed,
        remaining=remaining,
    )
