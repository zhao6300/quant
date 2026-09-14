from __future__ import annotations

from datetime import date

from mmqp.application.queries import LIVE_SNAPSHOT_ID
from mmqp.application.run_submission import ResearchRunRequest, RunSubmissionService


def test_contract_run_accepts_no_short_selling():
    request = ResearchRunRequest(
        snapshot_id=LIVE_SNAPSHOT_ID,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        base_currency="USD",
        factor_definition_version="factor",
        universe_version="universe",
        portfolio_definition_version="portfolio",
        strategy_version="strategy",
        transaction_cost_model_version="cost",
        risk_model_version="risk",
    )
    assert RunSubmissionService({LIVE_SNAPSHOT_ID}).submit(request).result_kind == "research_simulation"
