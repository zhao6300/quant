from __future__ import annotations

import pytest

from mmqp.domain.event_queue import BacktestBlueprint, BacktestImportError, run_backtest


def _blueprint(target: tuple[str, ...]) -> BacktestBlueprint:
    return BacktestBlueprint(
        name="test-blueprint",
        target=target,
    )


def test_run_backtest_applies_event_to_steps() -> None:
    blueprint = _blueprint(("1", "2", "3"))
    result = run_backtest(blueprint, ("1", "2", "3"))
    assert result.state == "PASS"
    assert result.pending == ("1", "2", "3")


def test_run_backtest_empty_blueprint_is_rejected() -> None:
    with pytest.raises(BacktestImportError):
        run_backtest(BacktestBlueprint(name="a", target=()), ())
