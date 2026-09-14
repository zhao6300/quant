from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mmqp.domain.experiments import RunComparison, compare_manifest


@dataclass(frozen=True, slots=True)
class _StubRun:
    run_id: str
    manifest_id: str
    completed_at: datetime
    alpha_weighted_return: Decimal
    turnover: Decimal


@given(
    alpha=st.one_of(st.just(Decimal("-10")), st.decimals(min_value="-100", max_value="100", places=6)),
    turnover=st.decimals(min_value="0", max_value="1"),
)
def test_comparison_complete(alpha, turnover):
    run = _StubRun("r", "m", datetime(2024, 1, 1, tzinfo=UTC), alpha, turnover)
    manifest = compare_manifest([run.manifest_id], [run.alpha_weighted_return])
    assert manifest == RunComparison(Decimal("0"), Decimal("0"))
