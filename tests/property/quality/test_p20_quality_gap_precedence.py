from __future__ import annotations

from typing import Literal, cast

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.application.quality import _aggregate
from mmqp.domain.quality import QualityIssue


@settings(max_examples=16, deadline=None)
@given(issues=st.lists(st.sampled_from((0, 1, 2)), max_size=5))
def test_quality_status_is_max_severity(issues: list[int]) -> None:
    severities = ("valid", "warning", "rejected")
    created = tuple(_issue("rule", severities[index]) for index in issues)
    result = _aggregate(created)

    assert len(result.quality_issues) == len(created)
    if created:
        assert (
            result.quality_status == max(created, key=lambda issue: severities.index(issue.severity)).severity
        )
    else:
        assert result.quality_status == "valid"


def _issue(rule_id: str, severity: str) -> QualityIssue:
    return QualityIssue(
        rule_id=rule_id,
        rule_version="v1",
        severity=cast(Literal["valid", "warning", "rejected"], severity),
        canonical_asset_id=None,
        observation_date=None,
        field=None,
        observed_value=None,
        expected_condition="expected",
        unavailable_dependency=None,
        evidence="test",
    )
