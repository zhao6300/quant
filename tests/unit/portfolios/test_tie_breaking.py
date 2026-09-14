from decimal import Decimal

from mmqp.domain.portfolios import build_score_weighted_portfolio


def test_equal_scores_break_ties_by_canonical_asset_id():
    scores_by_asset = {
        "c": (Decimal("1"), None, 0),
        "b": (Decimal("1"), None, 0),
    }
    portfolio = build_score_weighted_portfolio(scores_by_asset)
    assert portfolio.portfolio_id == "portfolio"
