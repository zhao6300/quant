from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.experiments import ExperimentRunner


@given(swap=st.booleans())
def test_manifest_replay_is_content_sensitive(swap):
    runner = ExperimentRunner()
    runs = {"a": ({"id": "first"}, {"id": "second"}), "b": ({"id": "third"},)}
    manifest = runner.compose(runs, seed=7)
    replayed = dict(runs)
    if swap:
        replayed["b"] = (
            {"id": "third"},
            {"id": "interference"},
        )
    if not swap:
        assert runner.replay(manifest, replayed, 7).manifest_id == manifest.manifest_id
    else:
        with pytest.raises(ValueError, match="replay mismatch"):
            runner.replay(manifest, replayed, 7)
