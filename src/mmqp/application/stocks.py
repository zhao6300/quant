from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StockChoice:
    symbol: str
    name: str
    market: str
    exchange: str
    currency: str


STOCK_CATALOG: dict[str, tuple[StockChoice, ...]] = {
    "A_SHARE": (
        StockChoice("600000.SS", "浦发银行", "A_SHARE", "SSE", "CNY"),
        StockChoice("600036.SS", "招商银行", "A_SHARE", "SSE", "CNY"),
        StockChoice("600519.SS", "贵州茅台", "A_SHARE", "SSE", "CNY"),
        StockChoice("601318.SS", "中国平安", "A_SHARE", "SSE", "CNY"),
        StockChoice("601288.SS", "农业银行", "A_SHARE", "SSE", "CNY"),
        StockChoice("601899.SS", "紫金矿业", "A_SHARE", "SSE", "CNY"),
        StockChoice("600900.SS", "长江电力", "A_SHARE", "SSE", "CNY"),
        StockChoice("601088.SS", "中国神华", "A_SHARE", "SSE", "CNY"),
        StockChoice("000001.SZ", "平安银行", "A_SHARE", "SZSE", "CNY"),
        StockChoice("000333.SZ", "美的集团", "A_SHARE", "SZSE", "CNY"),
        StockChoice("002594.SZ", "比亚迪", "A_SHARE", "SZSE", "CNY"),
        StockChoice("300750.SZ", "宁德时代", "A_SHARE", "SZSE", "CNY"),
    ),
    "HONG_KONG": (
        StockChoice("0700.HK", "腾讯控股", "HONG_KONG", "HKEX", "HKD"),
        StockChoice("9988.HK", "阿里巴巴-W", "HONG_KONG", "HKEX", "HKD"),
        StockChoice("0005.HK", "汇丰控股", "HONG_KONG", "HKEX", "HKD"),
        StockChoice("0388.HK", "香港交易所", "HONG_KONG", "HKEX", "HKD"),
        StockChoice("1299.HK", "友邦保险", "HONG_KONG", "HKEX", "HKD"),
        StockChoice("1810.HK", "小米集团-W", "HONG_KONG", "HKEX", "HKD"),
        StockChoice("3690.HK", "美团-W", "HONG_KONG", "HKEX", "HKD"),
        StockChoice("0941.HK", "中国移动", "HONG_KONG", "HKEX", "HKD"),
        StockChoice("1398.HK", "工商银行", "HONG_KONG", "HKEX", "HKD"),
        StockChoice("2318.HK", "中国平安", "HONG_KONG", "HKEX", "HKD"),
    ),
    "UNITED_STATES": (
        StockChoice("AAPL", "Apple", "UNITED_STATES", "NYSE", "USD"),
        StockChoice("MSFT", "Microsoft", "UNITED_STATES", "NASDAQ", "USD"),
        StockChoice("NVDA", "NVIDIA", "UNITED_STATES", "NASDAQ", "USD"),
        StockChoice("AMZN", "Amazon", "UNITED_STATES", "NASDAQ", "USD"),
        StockChoice("GOOGL", "Alphabet", "UNITED_STATES", "NASDAQ", "USD"),
        StockChoice("META", "Meta Platforms", "UNITED_STATES", "NASDAQ", "USD"),
        StockChoice("TSLA", "Tesla", "UNITED_STATES", "NASDAQ", "USD"),
        StockChoice("JPM", "JPMorgan Chase", "UNITED_STATES", "NYSE", "USD"),
        StockChoice("V", "Visa", "UNITED_STATES", "NYSE", "USD"),
        StockChoice("XOM", "Exxon Mobil", "UNITED_STATES", "NYSE", "USD"),
    ),
}


def stock_catalog(market: str, query: str | None = None, limit: int = 20) -> list[StockChoice]:
    choices = STOCK_CATALOG.get(market.upper(), ())
    normalized_query = (query or "").strip().casefold()
    if normalized_query:
        choices = tuple(
            choice
            for choice in choices
            if normalized_query in choice.name.casefold() or normalized_query in choice.symbol.casefold()
        )
    return list(choices[: min(max(limit, 1), 50)])
