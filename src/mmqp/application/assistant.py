from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal


AssistantActionKind = Literal[
    "goto_data",
    "goto_quote",
    "goto_backtest",
    "goto_overview",
    "goto_sources",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantAction:
    kind: AssistantActionKind
    title: str
    detail: str
    params: dict[str, Any]
    confirmation_required: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantContext:
    page_id: str = "overview"
    source_id: str = "sina-finance"
    source_name: str | None = None
    market_id: str = "a-share"
    market: str = "A_SHARE"
    exchange: str = "SSE"
    symbol: str = "600000.SS"
    stock_count: int | None = None
    trading_date: str | None = None
    history_days: int = 5
    dataset_name: str | None = None
    query_field: str | None = None
    query_value: str | None = None
    run_start_date: str | None = None
    run_end_date: str | None = None
    base_currency: str = "USD"
    workspace_count: int | None = None
    workspace_name: str | None = None
    workspace_path: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantRequest:
    message: str
    context: AssistantContext


@dataclass(frozen=True, slots=True, kw_only=True)
class AssistantResponse:
    answer: str
    mode: Literal["deterministic", "llm"]
    provider: str
    actions: tuple[AssistantAction, ...]
    context_used: AssistantContext


class ResearchAssistantService:
    provider = "deterministic-intent"
    mode = "deterministic"

    def respond(self, request: AssistantRequest) -> AssistantResponse:
        message = request.message.strip()
        context = request.context

        if _mentions(["工作区", "新建", "路径"], message):
            answer = (
                "工作区建议放在一个绝对目录下。先填路径与显示名称，"
                "再由你在总览页确认创建。"
            )
            actions = (
                _overview_action(),
                AssistantAction(
                    kind="goto_overview",
                    title="打开工作区准备",
                    detail="跳转总览并聚焦创建表单。",
                    params={"focus": "workspace"},
                ),
            )
            return AssistantResponse(
                answer=answer,
                mode=self.mode,
                provider=self.provider,
                actions=actions,
                context_used=context,
            )

        if _mentions(["回测", "研究运行", "实验"], message):
            answer = (
                "回测属于写研究记录的操作。我会先准备开始/结束日期和基准货币，"
                "提交前仍需要你确认研究窗口与版本引用。"
            )
            actions = (
                _backtest_action(
                    context.run_start_date,
                    context.run_end_date,
                    context.base_currency,
                ),
                _overview_action(),
            )
            return AssistantResponse(
                answer=answer,
                mode=self.mode,
                provider=self.provider,
                actions=actions,
                context_used=context,
            )

        if _mentions(["数据", "快照", "资产", "净值", "基本面"], message):
            dataset = _dataset(message, context)
            field, value = _filter(message, context)
            actions = (_data_action(dataset, field, value),)
            answer = (
                f"建议查询 {dataset}。"
                + (f"过滤条件为 {field}={value}。" if field else "本页可按数据集直接查询。")
                + "点击操作会应用查询条件，查询由本地不可变快照执行。"
            )
            return AssistantResponse(
                answer=answer,
                mode=self.mode,
                provider=self.provider,
                actions=actions,
                context_used=context,
            )

        if _mentions(["数据源", "供给", "provider"], message):
            actions = (_sources_action(),)
            answer = "先查看数据源目录，再选择一个已连接行情源进入行情终端。"
            return AssistantResponse(
                answer=answer,
                mode=self.mode,
                provider=self.provider,
                actions=actions,
                context_used=context,
            )

        if _mentions(["日历", "规则", "lot", "tick", "结算"], message):
            actions = (_sources_action(),)
            answer = "日历和规则属于数据准备的一部分；可以在数据层查询市场规则快照后再进入运行。"
            return AssistantResponse(
                answer=answer,
                mode=self.mode,
                provider=self.provider,
                actions=actions,
                context_used=context,
            )

        market_id = _market_id(message, context)
        symbol = _symbol(message, market_id, context)
        actions = (_quote_action(symbol, market_id, context),)
        answer = (
            f"已准备查看 {symbol} 的真实行情。"
            "应用后加载所选数据源的单日 OHLCV，并读取历史 K 线。"
        )
        return AssistantResponse(
            answer=answer,
            mode=self.mode,
            provider=self.provider,
            actions=actions,
            context_used=context,
        )


def _mentions(needles: tuple[str, ...] | list[str], message: str) -> bool:
    translated = [item.lower() for item in needles]
    return any(item in message.lower() for item in translated)


def _symbol(message: str, market_id: str, context: AssistantContext) -> str:
    candidates = re.findall(r"\b[A-Za-z0-9.-]{1,16}\b", message)
    preferred: str | None = None
    for candidate in candidates:
        if candidate.lower() in {"a", "us", "hk", "ai", "mmqp"}:
            continue
        if ".ss" in candidate.lower() or ".sz" in candidate.lower() or ".hk" in candidate.lower():
            preferred = candidate.upper()
            break
    if preferred is None:
        for candidate in candidates:
            if candidate.isalpha():
                preferred = candidate.upper()
                break
    if preferred is None:
        for candidate in candidates:
            if re.fullmatch(r"\d{6}", candidate):
                preferred = f"{candidate}.SS"
                break
    return preferred or context.symbol


def _market_id(message: str, context: AssistantContext) -> str:
    if _mentions(["港股", "香港", "hong kong"], message):
        return "hong-kong"
    if _mentions(["美股", "united states", "nyse"], message):
        return "united-states"
    if _mentions(["a股", "a 股", "上海", "深证"], message):
        return "a-share"
    return context.market_id


def _dataset(message: str, context: AssistantContext) -> str:
    mapping = {
        "资产": "ASSET_MASTER",
        "资产主": "ASSET_MASTER",
        "日k": "DAILY_BAR",
        "日线": "DAILY_BAR",
        "净值": "FUND_NAV",
        "基本面": "FUNDAMENTAL_FACT",
        "交易历": "TRADING_CALENDAR",
        "日历": "TRADING_CALENDAR",
        "规则": "MARKET_RULE_PROFILE",
        "估值历": "VALUATION_CALENDAR",
        "分红": "CORPORATE_ACTION",
        "公司行为": "CORPORATE_ACTION",
    }
    for needle, dataset in mapping.items():
        if needle in message.lower():
            return dataset
    return context.dataset_name or "ASSET_MASTER"


def _filter(message: str, context: AssistantContext) -> tuple[str | None, str | None]:
    if "equity" in message.lower() or "股票" in message:
        return "asset_type", "EQUITY"
    if "美元" in message or "usd" in message.lower():
        return "trading_currency", "USD"
    if "人民币" in message or "cny" in message.lower():
        return "trading_currency", "CNY"
    return context.query_field or None, context.query_value or None


def _data_action(dataset: str, field: str | None, value: str | None) -> AssistantAction:
    detail = f"{dataset}" + (f" · {field}={value}" if field and value else "")
    return AssistantAction(
        kind="goto_data",
        title="应用数据查询",
        detail=detail,
        params={"dataset": dataset, "field": field, "value": value},
    )


def _quote_action(symbol: str, market_id: str, context: AssistantContext) -> AssistantAction:
    return AssistantAction(
        kind="goto_quote",
        title="打开行情终端",
        detail=f"{symbol} · {market_id}",
        params={
            "symbol": symbol,
            "market_id": market_id,
            "source_id": context.source_id,
            "trading_date": context.trading_date,
            "history_days": context.history_days,
        },
    )


def _backtest_action(
    start_date: str | None,
    end_date: str | None,
    base_currency: str,
) -> AssistantAction:
    return AssistantAction(
        kind="goto_backtest",
        title="打开研究运行",
        detail=f"{start_date or '未设置'} — {end_date or '未设置'}",
        params={
            "start_date": start_date,
            "end_date": end_date,
            "base_currency": base_currency,
        },
        confirmation_required=True,
    )


def _overview_action() -> AssistantAction:
    return AssistantAction(
        kind="goto_overview",
        title="打开研究总览",
        detail="准备工作区。",
        params={},
    )


def _sources_action() -> AssistantAction:
    return AssistantAction(
        kind="goto_sources",
        title="打开数据源目录",
        detail="查看已连接供给。",
        params={},
    )
