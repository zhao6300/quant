from __future__ import annotations

from mmqp.domain.experiments import ExperimentRunner


def test_runner_replay_is_content_sensitive():
    runner = ExperimentRunner()
    runs = {"a": ({"auto": "1"}, {"api": "2"})}
    manifest = runner.submit(runs, seed=7)
    runner.replay(manifest, runs, 7)
