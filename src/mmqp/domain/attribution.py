from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ExternalCashFlow:
    timestamp: datetime
    amount: Decimal

    def validate(self) -> None:
        if not self.amount.is_finite():
            raise ValueError("external cash flow must be finite")


@dataclass(frozen=True, slots=True)
class PeriodAttribution:
    portfolio_return: Decimal
    asset_contributions: dict[str, Decimal]
    cash_contribution: Decimal
    transaction_cost_drag: Decimal
    residual: Decimal


def periodic_return(
    beginning_value: Decimal,
    ending_value: Decimal,
    flows: Sequence[ExternalCashFlow],
    period_start: datetime,
    period_end: datetime,
) -> Decimal | None:
    if period_start >= period_end:
        return None
    for flow in flows:
        flow.validate()
    if not beginning_value.is_finite() or not ending_value.is_finite():
        return None
    ordered = sorted(flows, key=lambda flow: flow.timestamp)
    if ordered and ordered[-1].timestamp > period_end:
        return None
    period_length = Decimal((period_end - period_start).total_seconds())
    weighted_flows = sum(
        (
            flow.amount
            * (Decimal(1) - Decimal((flow.timestamp - period_start).total_seconds()) / period_length)
            for flow in ordered
        ),
        Decimal(0),
    )
    denominator = beginning_value + weighted_flows
    if denominator <= Decimal(0):
        return None
    total_flow = sum((flow.amount for flow in ordered), Decimal(0))
    return (ending_value - beginning_value - total_flow) / denominator


def cash_contribution(weight: Decimal, cash_return: Decimal) -> Decimal:
    return weight * cash_return


def transaction_cost_drag(transaction_cost: Decimal, denominator: Decimal) -> Decimal:
    if transaction_cost < Decimal(0) or denominator <= Decimal(0):
        raise ValueError("transaction cost and denominator must be valid")
    return -transaction_cost / denominator


def asset_contributions(
    beginning_weights: Mapping[str, Decimal],
    asset_returns: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    return {
        asset: beginning_weights[asset] * asset_returns[asset]
        for asset in sorted(beginning_weights)
        if asset in asset_returns
    }


def build_period_attribution(
    portfolio_return: Decimal,
    beginning_weights: Mapping[str, Decimal],
    asset_returns: Mapping[str, Decimal],
    cash_weight: Decimal,
    cash_return: Decimal,
    transaction_cost: Decimal,
) -> PeriodAttribution:
    contributions = asset_contributions(beginning_weights, asset_returns)
    cash = cash_contribution(cash_weight, cash_return)
    cost = transaction_cost_drag(transaction_cost, Decimal(1))
    residual = (
        portfolio_return
        - sum(contributions.values(), Decimal(0))
        - cash
        - cost
    )
    return PeriodAttribution(
        portfolio_return=portfolio_return,
        asset_contributions=contributions,
        cash_contribution=cash,
        transaction_cost_drag=cost,
        residual=residual,
    )


@dataclass(frozen=True, slots=True)
class BrinsonFachlerEffect:
    allocation: Decimal
    selection: Decimal
    interaction: Decimal


def brinson_fachler(
    groups: Sequence[str],
    portfolio_weights: Mapping[str, Decimal],
    benchmark_weights: Mapping[str, Decimal],
    portfolio_returns: Mapping[str, Decimal],
    benchmark_returns: Mapping[str, Decimal],
    portfolio_return: Decimal,
    benchmark_return: Decimal,
) -> tuple[dict[str, BrinsonFachlerEffect], Decimal]:
    effects: dict[str, BrinsonFachlerEffect] = {}
    total = Decimal(0)
    for group in sorted(groups):
        portfolio_weight = portfolio_weights[group]
        benchmark_weight = benchmark_weights[group]
        portfolio_group_return = portfolio_returns[group]
        benchmark_group_return = benchmark_returns[group]
        allocation = (portfolio_weight - benchmark_weight) * (
            benchmark_group_return - benchmark_return
        )
        selection = benchmark_weight * (portfolio_group_return - benchmark_group_return)
        interaction = (portfolio_weight - benchmark_weight) * (
            portfolio_group_return - benchmark_group_return
        )
        effects[group] = BrinsonFachlerEffect(
            allocation=allocation,
            selection=selection,
            interaction=interaction,
        )
        total += allocation + selection + interaction
    residual = portfolio_return - benchmark_return - total
    return effects, residual


def local_fx_return(local: Decimal, fx: Decimal) -> Decimal:
    return (Decimal(1) + local) * (Decimal(1) + fx) - Decimal(1)


@dataclass(frozen=True, slots=True)
class LocalFxEffect:
    local: Decimal
    fx: Decimal


def local_fx_effect(weight: Decimal, local: Decimal, fx: Decimal) -> LocalFxEffect:
    return LocalFxEffect(local=weight * local, fx=weight * (Decimal(1) + local) * fx)


@dataclass(frozen=True, slots=True)
class LinkedAttribution:
    contributions: dict[str, Decimal]
    total_return: Decimal
    residual: Decimal


def linked_attribution(
    periods: Sequence[tuple[Decimal, Mapping[str, Decimal]]],
) -> LinkedAttribution:
    if not periods:
        raise ValueError("linked attribution requires one period")
    components = sorted(
        {component for _return, values in periods for component in values}
    )
    linked = {component: Decimal(0) for component in components}
    total = Decimal(1)
    for period_return, period_contributions in periods:
        total *= Decimal(1) + period_return
        for component in components:
            linked[component] = linked[component] * (Decimal(1) + period_return) + period_contributions[component]
    total_return = total - Decimal(1)
    residual = sum(linked.values(), Decimal(0)) - total_return
    if abs(residual) > Decimal("1e-10"):
        raise ValueError("linked attribution residual exceeds tolerance")
    return LinkedAttribution(contributions=linked, total_return=total_return, residual=residual)
