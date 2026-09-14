from mmqp.domain.backtest import BacktestPlan, BacktestResult, TradingPlan, schedule_requests


def prepare_backtest(plan: BacktestPlan) -> TradingPlan:
    return schedule_requests(plan)


def execute_backtest(plan: BacktestPlan) -> BacktestResult:
    from mmqp.domain.backtest import run_backtest

    return run_backtest(plan)
