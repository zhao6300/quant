from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from mmqp.application.factor_evaluation import FactorEvaluationService
from mmqp.domain.factor_evaluation import CrossSection, FactorEvaluationRequest

DECISION_AT = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)


def _cross_section(factor_date: date, factor_seed: int) -> CrossSection:
    factor_values = {
        "ASSET-A": Decimal(factor_seed),
        "ASSET-B": Decimal(factor_seed + 10),
    }
    future_returns = {asset_id: factor_value * 2 for asset_id, factor_value in factor_values.items()}
    return CrossSection(
        factor_values_by_asset=factor_values,
        future_returns_by_asset=future_returns,
        factor_date=factor_date,
        decision_at=DECISION_AT,
    )


def test_report_exposes_series_date_and_counts() -> None:
    cross_section = _cross_section(date(2024, 1, 2), factor_seed=1)
    report = FactorEvaluationService().evaluate(
        FactorEvaluationRequest(
            evaluation_id="factor-report-1",
            universe_version="universe-1",
            decision_at=DECISION_AT,
            holding_period=1,
            quantile_count=2,
            cross_sections=(cross_section,),
        )
    )
    assert report.factor_dates == (date(2024, 1, 2),)
    assert report.decision_at_timestamps == (cross_section.decision_at,)
    assert report.aligned_count == 2
    assert report.missing_count == 0
    assert report.coverage_ratio == Decimal("1")
    assert [point.value for point in report.pearson_series] == [Decimal("1")]
    assert [point.value for point in report.spearman_series] == [Decimal("1")]
