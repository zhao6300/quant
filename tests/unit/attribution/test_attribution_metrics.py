from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from mmqp.domain.attribution import (
    ExternalCashFlow,
    asset_contributions,
    brinson_fachler,
    build_period_attribution,
    cash_contribution,
    linked_attribution,
    local_fx_effect,
    local_fx_return,
    periodic_return,
    transaction_cost_drag,
)


def test_periodic_return_uses_timed_flows() -> None:
    return_ = periodic_return(
        Decimal("100"),
        Decimal("120"),
        (ExternalCashFlow(datetime(2024, 1, 1, 12, 0, tzinfo=UTC), Decimal("10")),),
        datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        datetime(2024, 1, 2, 0, 0, tzinfo=UTC),
    )
    expected = (Decimal("120") - Decimal("100") - Decimal("10")) / (Decimal("100") + Decimal("5"))
    assert return_ == expected


def test_asset_cash_and_cost_contributions() -> None:
    contributions = asset_contributions({"A": Decimal("0.5")}, {"A": Decimal("0.1")})
    assert contributions == {"A": Decimal("0.05")}
    assert cash_contribution(Decimal("0.25"), Decimal("0.02")) == Decimal("0.005")
    assert transaction_cost_drag(Decimal("1"), Decimal("100")) == Decimal("-0.01")


def test_period_attribution_contributions_reconcile() -> None:
    result = build_period_attribution(
        Decimal("0.055"),
        {"A": Decimal("0.5")},
        {"A": Decimal("0.1")},
        Decimal("0.25"),
        Decimal("0.02"),
        Decimal("0"),
    )
    assert result.asset_contributions["A"] == Decimal("0.05")
    assert result.cash_contribution == Decimal("0.005")
    assert result.transaction_cost_drag == Decimal("0")
    assert abs(result.residual) <= Decimal("1e-10")


def test_brisson_fachler_effects_reconcile() -> None:
    effects, residual = brinson_fachler(
        ("growth", "defensive"),
        {"growth": Decimal("0.7"), "defensive": Decimal("0.3")},
        {"growth": Decimal("0.3"), "defensive": Decimal("0.7")},
        {"growth": Decimal("0.2"), "defensive": Decimal("0.2")},
        {"growth": Decimal("0.1"), "defensive": Decimal("0.1")},
        Decimal("0.2"),
        Decimal("0.1"),
    )
    assert abs(residual) <= Decimal("1e-10")
    assert effects["growth"].allocation == Decimal("0")
    assert effects["growth"].selection > Decimal("0")
    assert effects["growth"].interaction > Decimal("0")


def test_local_fx_identity_is_exact() -> None:
    assert local_fx_return(Decimal("0.2"), Decimal("0.1")) == Decimal("0.32")
    effect = local_fx_effect(Decimal("0.5"), Decimal("0.2"), Decimal("0.1"))
    assert effect.local == Decimal("0.1")
    assert effect.fx == Decimal("0.06")


def test_linked_attribution_reconciles() -> None:
    linked = linked_attribution(
        [
            (Decimal("0.1"), {"A": Decimal("0.05"), "B": Decimal("0.05")}),
            (Decimal("0.1"), {"A": Decimal("0.06"), "B": Decimal("0.04")}),
        ]
    )
    expected_total = Decimal("0.21")
    assert abs(linked.residual) <= Decimal("1e-10")
    assert abs(linked.total_return - expected_total) <= Decimal("1e-10")
