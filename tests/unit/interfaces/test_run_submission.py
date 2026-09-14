from datetime import date

import pytest

from mmqp.application.queries import LIVE_SNAPSHOT_ID
from mmqp.application.run_submission import (
    ResearchRunRequest,
    RunSubmissionService,
    RunSubmissionValidationError,
)


def _request(**changes: object) -> ResearchRunRequest:
    values = {
        "snapshot_id": LIVE_SNAPSHOT_ID,
        "start_date": date(2024, 1, 1),
        "end_date": date(2024, 1, 31),
        "base_currency": "USD",
        "factor_definition_version": "factor-v1",
        "universe_version": "universe-v1",
        "portfolio_definition_version": "portfolio-v1",
        "strategy_version": "strategy-v1",
        "transaction_cost_model_version": "cost-v1",
        "risk_model_version": "risk-v1",
    }
    values.update(changes)
    return ResearchRunRequest(**values)


def test_empty_version_and_reversed_dates_are_rejected_without_runner() -> None:
    request = _request(
        factor_definition_version=" ",
        universe_version="",
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 1),
    )
    with pytest.raises(RunSubmissionValidationError) as error:
        RunSubmissionService([LIVE_SNAPSHOT_ID]).submit(request)
    assert "factor_definition_version" in error.value.fields
    assert "universe_version" in error.value.fields
    assert error.value.error_codes == ["date_range.invalid", "version.missing"]
