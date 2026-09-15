import { useCallback, useEffect, useRef, useState } from "react";
import { ApiClient } from "./api/client";
import type {
  EvaluatedTrade,
  MarketRuleProfile,
  PlatformStatus,
  QueryDataset,
  QueryResult,
  ResearchRunRequest,
  RunSubmissionReceipt,
  TradingCalendarVersion,
  ValuationCalendarVersion,
  Workspace,
  DataSource,
  SourceTicker,
  SourceHistoryBar,
  StockChoice,
} from "./types";

const client = new ApiClient();

const MARKET_OPTIONS = [
  { id: "a-share", label: "A股", market: "A_SHARE", exchange: "SSE" },
  { id: "hong-kong", label: "港股", market: "HONG_KONG", exchange: "HKEX" },
  {
    id: "united-states",
    label: "美股",
    market: "UNITED_STATES",
    exchange: "NYSE",
  },
] as const;

type MarketOption = (typeof MARKET_OPTIONS)[number];

const DATASETS: QueryDataset[] = [
  "ASSET_MASTER",
  "DAILY_BAR",
  "FUND_NAV",
  "FUNDAMENTAL_FACT",
  "TRADING_CALENDAR",
  "MARKET_RULE_PROFILE",
  "VALUATION_CALENDAR",
  "CORPORATE_ACTION",
];

const FILTER_OPTIONS: Partial<Record<QueryDataset, readonly string[]>> = {
  ASSET_MASTER: ["asset_type", "market", "name"],
  DAILY_BAR: ["trading_currency", "provider", "provenance_id"],
  FUND_NAV: ["pricing_currency", "provider", "provenance_id"],
  FUNDAMENTAL_FACT: ["metric_name", "unit", "provider", "provenance_id"],
  TRADING_CALENDAR: ["version_id", "market", "exchange", "timezone"],
  MARKET_RULE_PROFILE: ["version_id", "market", "exchange", "asset_type"],
  VALUATION_CALENDAR: ["version_id", "market", "timezone"],
  CORPORATE_ACTION: [
    "version_id",
    "canonical_asset_id",
    "event_id",
    "action_type",
    "provenance_id",
  ],
};

type RunVersionFields = Omit<
  ResearchRunRequest,
  "snapshot_id" | "start_date" | "end_date" | "base_currency"
>;

const RUN_FIELD_LABELS: { key: keyof RunVersionFields; label: string }[] = [
  { key: "factor_definition_version", label: "因子定义" },
  { key: "universe_version", label: "宇宙" },
  { key: "portfolio_definition_version", label: "组合定义" },
  { key: "strategy_version", label: "策略" },
  { key: "transaction_cost_model_version", label: "交易成本模型" },
  { key: "risk_model_version", label: "风险模型" },
];

const NAVIGATION = [
  {
    id: "overview",
    label: "总览",
    title: "研究总览",
    subtitle: "Research Control",
    description: "工作区、数据和运行状态集中处理。",
  },
  {
    id: "data",
    label: "数据",
    title: "数据查询",
    subtitle: "Immutable Snapshots",
    description: "按快照读取和过滤本地研究数据。",
  },
  {
    id: "factor",
    label: "因子",
    title: "多市场日历与规则",
    subtitle: "Calendar Rules",
    description: "查询市场语义并评估研究约束。",
  },
  {
    id: "backtest",
    label: "回测",
    title: "研究运行",
    subtitle: "Research Simulation",
    description: "生成科研模拟回执，不发送真实订单。",
  },
  {
    id: "sources",
    label: "数据源",
    title: "外部数据源",
    subtitle: "Integrated Sources",
    description: "接入目录化的免费本地/远端研究源。",
  },
  {
    id: "quote",
    label: "行情",
    title: "行情快照",
    subtitle: "Market Quote",
    description: "选择已接入的数据源并读取单日行情。",
  },
] as const;

type NavigationId = (typeof NAVIGATION)[number]["id"];

function marketById(id: string): MarketOption {
  return MARKET_OPTIONS.find((option) => option.id === id) ?? MARKET_OPTIONS[0];
}

function defaultMarketSymbol(id: string): string {
  const market = marketById(id);
  if (market.market === "HONG_KONG") return "0700.HK";
  if (market.market === "UNITED_STATES") return "AAPL";
  return "600000.SS";
}

function quoteNumber(value: string): string {
  const numeric = Number(value);
  return Number.isFinite(numeric)
    ? numeric.toLocaleString("en-US", { maximumFractionDigits: 6 })
    : value;
}

function preferredDailyBarSource(
  sources: DataSource[] | null | undefined,
  marketId: string = "a-share",
) {
  const preferred =
    sources?.find((source) => source.id === (marketId === "a-share" ? "sina-finance" : "yahoo-finance")) ??
    sources?.find((source) => source.category === "market");
  return preferred ?? null;
}

function App() {
  const [socialData, setSocialData] = useState("Loading");
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [sources, setSources] = useState<DataSource[] | null>(null);
  const [tradingCalendar, setTradingCalendar] =
    useState<TradingCalendarVersion | null>(null);
  const [valuationCalendar, setValuationCalendar] =
    useState<ValuationCalendarVersion | null>(null);
  const [marketRule, setMarketRule] = useState<MarketRuleProfile | null>(null);
  const [marketError, setMarketError] = useState<string | null>(null);
  const [selectedMarketId, setSelectedMarketId] = useState("a-share");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [orderQuantity, setOrderQuantity] = useState("1005");
  const [orderPrice, setOrderPrice] = useState("10.017");
  const [referencePrice, setReferencePrice] = useState("10.00");
  const [evaluation, setEvaluation] = useState<EvaluatedTrade | null>(null);
  const [path, setPath] = useState("");
  const [datasetName, setDatasetName] = useState<QueryDataset>("ASSET_MASTER");
  const [queryField, setQueryField] = useState("asset_type");
  const [queryValue, setQueryValue] = useState("EQUITY");
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [runWindowStart, setRunWindowStart] = useState("");
  const [runWindowEnd, setRunWindowEnd] = useState("");
  const [runBaseCurrency, setRunBaseCurrency] = useState("USD");
  const [runVersions, setRunVersions] = useState<RunVersionFields>({
    factor_definition_version: "",
    universe_version: "",
    portfolio_definition_version: "",
    strategy_version: "",
    transaction_cost_model_version: "",
    risk_model_version: "",
  });
  const [runReceipt, setRunReceipt] = useState<RunSubmissionReceipt | null>(
    null,
  );
  const [runError, setRunError] = useState<string | null>(null);
  const [runSubmitting, setRunSubmitting] = useState(false);
  const [activeSourceId, setActiveSourceId] = useState<string>(
    preferredDailyBarSource(undefined)?.id ?? "sina-finance",
  );
  const [symbol, setSymbol] = useState<string>(defaultMarketSymbol("a-share"));
  const [stockChoices, setStockChoices] = useState<StockChoice[]>([]);
  const [stockSearch, setStockSearch] = useState("");
  const [stockLoading, setStockLoading] = useState(false);
  const [stockError, setStockError] = useState<string | null>(null);
  const [quoteDate, setQuoteDate] = useState<string>(
    new Date().toLocaleDateString("en-CA"),
  );
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [quote, setQuote] = useState<SourceTicker | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [quoteFallback, setQuoteFallback] = useState<string | null>(null);
  const [quoteHistory, setQuoteHistory] = useState<SourceHistoryBar[] | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyFallback, setHistoryFallback] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [activePageId, setActivePageId] = useState<NavigationId>("overview");

  const activeMarket = marketById(selectedMarketId);
  const activeNavigation =
    NAVIGATION.find((page) => page.id === activePageId) ?? NAVIGATION[0];
  const activeSource =
    sources?.find((source) => source.id === activeSourceId) ?? sources?.[0];
  const autoQuoteKeyRef = useRef("");
  const readHistoryRef = useRef("");

  const setSourceFocus = useCallback(
    (source: DataSource) => {
      if (source.category !== "market") {
        return;
      }
      setActiveSourceId(source.id);
      setSelectedProvider(source.id);
      setSymbol(defaultMarketSymbol(selectedMarketId));
      setQuote(null);
      setQuoteError(null);
      setQuoteFallback(null);
      setQuoteHistory(null);
      setHistoryFallback(null);
      autoQuoteKeyRef.current = [
        source.id,
        selectedMarketId,
        defaultMarketSymbol(selectedMarketId),
        quoteDate,
      ].join("|");
      setActivePageId("quote");
    },
    [quoteDate, selectedMarketId],
  );

  const readSourceHistory = useCallback(
    async (days: number) => {
      const requestKey = [activeSourceId, selectedMarketId, symbol, quoteDate, days].join("|");
      if (readHistoryRef.current === requestKey) return;
      readHistoryRef.current = requestKey;
      setHistoryLoading(true);
      setHistoryError(null);
      setQuoteHistory(null);
      setHistoryFallback(null);
      let fallbackNote: string | null = null;
      try {
        try {
          const result = await client.sourceHistory(activeSourceId, {
            market: activeMarket.market,
            exchange: activeMarket.exchange,
            symbol,
            trading_date: quoteDate,
          });
          setQuoteHistory(result.bars);
          setHistoryError(null);
        } catch (primaryError) {
          if (activeSourceId === "yahoo-finance") {
            throw primaryError;
          }
          fallbackNote = "Yahoo Finance";
          const fallback = await client.sourceHistory("yahoo-finance", {
            market: activeMarket.market,
            exchange: activeMarket.exchange,
            symbol,
            trading_date: quoteDate,
          });
          setQuoteHistory(fallback.bars);
          setHistoryError(null);
          setHistoryFallback(fallbackNote);
        }
      } catch (error) {
        setQuoteHistory(null);
        setHistoryError(error instanceof Error ? error.message : "读取历史失败。");
      } finally {
        setHistoryLoading(false);
      }
    },
    [
      activeSourceId,
      activeMarket.exchange,
      activeMarket.market,
      quoteDate,
      selectedMarketId,
      symbol,
    ],
  );

  const readSourceQuote = useCallback(async (symbolOverride?: string) => {
    const requestedSymbol = symbolOverride ?? symbol;
    if (!requestedSymbol) {
      setQuoteError("请输入标的代码。");
      return;
    }
    setQuote(null);
    setQuoteError(null);
    setQuoteFallback(null);
    setQuoteLoading(true);
    try {
      const quotation = await client.sourceQuote(
        activeSourceId,
        {
          market: activeMarket.market,
          exchange: activeMarket.exchange,
          symbol: requestedSymbol,
          trading_date: quoteDate,
        },
      );
      setQuote(quotation);
      setSelectedProvider(activeSourceId);
      setQuoteError(null);
    } catch (error) {
      if (activeSourceId !== "yahoo-finance") {
        try {
          const fallback = await client.sourceQuote("yahoo-finance", {
            market: activeMarket.market,
            exchange: activeMarket.exchange,
            symbol: requestedSymbol,
            trading_date: quoteDate,
          });
          setQuote(fallback);
          setQuoteFallback("Yahoo Finance");
          setQuoteError(null);
        } catch (fallbackError) {
          setQuote(null);
          setQuoteError(
            fallbackError instanceof Error ? fallbackError.message : "读取行情失败。",
          );
        }
      } else {
        setQuote(null);
        setQuoteError(error instanceof Error ? error.message : "读取行情失败。");
      }
    } finally {
      setQuoteLoading(false);
    }
  }, [
    activeSourceId,
    activeMarket.exchange,
    activeMarket.market,
    quoteDate,
    symbol,
  ]);

  const chooseStock = useCallback(
    (choice: StockChoice) => {
      setSymbol(choice.symbol);
      setQuote(null);
      setQuoteError(null);
      setQuoteFallback(null);
      setQuoteHistory(null);
      setHistoryError(null);
      setHistoryFallback(null);
      autoQuoteKeyRef.current = [
        activeSourceId,
        selectedMarketId,
        choice.symbol,
        quoteDate,
      ].join("|");
      void readSourceQuote(choice.symbol);
    },
    [
      activeSourceId,
      quoteDate,
      readSourceQuote,
      selectedMarketId,
    ],
  );

  useEffect(() => {
    if (activePageId !== "quote" || quoteLoading || quote) return;
    if (activeSource?.category !== "market") return;
    const requestKey = [
      activeSourceId,
      selectedMarketId,
      symbol,
      quoteDate,
    ].join("|");
    if (autoQuoteKeyRef.current === requestKey) return;
    autoQuoteKeyRef.current = requestKey;
    void readSourceQuote();
  }, [
    activePageId,
    activeSource?.category,
    activeSourceId,
    quote,
    quoteDate,
    quoteLoading,
    readSourceQuote,
    selectedProvider,
    selectedMarketId,
    symbol,
  ]);

  useEffect(() => {
    if (activePageId !== "quote") return;
    const controller = new AbortController();
    const search = stockSearch;
    setStockChoices([]);
    setStockLoading(true);
    const timer = window.setTimeout(() => {
      client
        .stockChoices(activeMarket.market, search)
        .then((result) => {
          if (!controller.signal.aborted) {
            setStockChoices(result.stocks);
            setStockError(null);
          }
        })
        .catch(() => {
          if (!controller.signal.aborted) setStockError("股票列表不可用。");
        })
        .finally(() => {
          if (!controller.signal.aborted) setStockLoading(false);
        });
    }, search ? 180 : 0);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
      setStockLoading(false);
    };
  }, [activePageId, activeMarket.market, stockSearch]);

  useEffect(() => {
    const preferred = preferredDailyBarSource(sources, selectedMarketId);
    if (!preferred || preferred.id === activeSourceId) return;
    setActiveSourceId(preferred.id);
  }, [activeSourceId, sources, selectedMarketId]);

  useEffect(() => {
    if (quote && !quoteHistory && !historyLoading) {
      void readSourceHistory(5);
    }
  }, [quote, quoteHistory, readSourceHistory, historyLoading]);

  const evaluate = useCallback(async () => {
    const isActive = activeMarket.market === "A_SHARE";
    setEvaluation(
      await client.evaluateTrade({
        market: activeMarket.market,
        exchange: activeMarket.exchange,
        asset_type: "EQUITY",
        trade_date: effectiveDate || new Date().toLocaleDateString("en-CA"),
        requested_quantity: orderQuantity,
        requested_price: orderPrice,
        reference_price: isActive ? referencePrice : undefined,
        market_data_price_limit_percent: isActive ? referencePrice : undefined,
        market_data_price_band_percent: isActive ? undefined : referencePrice,
        sellable_quantity: orderQuantity,
      }),
    );
  }, [
    activeMarket.exchange,
    activeMarket.market,
    effectiveDate,
    orderPrice,
    orderQuantity,
    referencePrice,
  ]);

  const refresh = useCallback(async () => {
    try {
      const [fetchedStatus, fetchedWorkspaces, fetchedSources] =
        await Promise.all([
          client.status(),
          client.workspaces(),
          client.dataSources(),
        ]);
      setStatus(fetchedStatus);
      setWorkspaces(fetchedWorkspaces);
      setSources(fetchedSources);
      setSocialData(`Online · v${fetchedStatus.platform_version}`);
      setError(null);
    } catch {
      setSocialData("Offline");
      setError("无法连接本地研究服务。请先启动后端。");
    }
  }, []);

  const runQuery = useCallback(async () => {
    try {
      const result = await client.queryDataset({
        dataset: datasetName,
        filters: queryValue
          ? [{ field: queryField, values: [queryValue] }]
          : [],
      });
      setQueryResult(result);
      setQueryError(null);
    } catch {
      setQueryResult(null);
      setQueryError("查询失败。");
    }
  }, [datasetName, queryField, queryValue]);


  const submitRun = useCallback(async () => {
    if (!runWindowStart || !runWindowEnd) {
      setRunError("请选择研究窗口的开始和结束日期。");
      return;
    }
    if (runWindowStart > runWindowEnd) {
      setRunError("研究窗口的开始日期必须不晚于结束日期。");
      return;
    }
    setRunSubmitting(true);
    try {
      const receipt = await client.submitRun({
        snapshot_id: "LIVE",
        start_date: runWindowStart,
        end_date: runWindowEnd,
        base_currency: runBaseCurrency,
        ...runVersions,
      });
      setRunReceipt(receipt);
      setRunError(null);
    } catch {
      setRunReceipt(null);
      setRunError("运行提交失败。");
    } finally {
      setRunSubmitting(false);
    }
  }, [runBaseCurrency, runVersions, runWindowEnd, runWindowStart]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const loadMarketState = useCallback(async () => {
    const today = new Date().toLocaleDateString("en-CA");
    const requestedDate = effectiveDate || today;
    try {
      const [calendar, valuation] = await Promise.all([
        client.tradingCalendar(
          activeMarket.market,
          activeMarket.exchange,
          requestedDate,
        ),
        client.valuationCalendar(activeMarket.market, requestedDate),
      ]);
      setTradingCalendar(calendar);
      setValuationCalendar(valuation);
      try {
        setMarketRule(
          await client.marketRule(
            activeMarket.market,
            activeMarket.exchange,
            "EQUITY",
            requestedDate,
          ),
        );
      } catch {
        setMarketRule(null);
      }
      setMarketError(null);
    } catch {
      setTradingCalendar(null);
      setValuationCalendar(null);
      setMarketRule(null);
      setMarketError("没有找到该市场日期的日历或规则。");
    }
  }, [activeMarket.exchange, activeMarket.market]);

  useEffect(() => {
    void loadMarketState();
  }, [loadMarketState]);

  const createWorkspace = useCallback(async () => {
    if (!path.trim()) {
      setError("请输入工作区绝对路径。");
      return;
    }
    setSubmitting(true);
    try {
      await client.createWorkspace(
        path.trim(),
        displayName.trim() || undefined,
      );
      setPath("");
      setDisplayName("");
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "工作区创建失败。");
    } finally {
      setSubmitting(false);
    }
  }, [displayName, path, refresh]);

  return (
    <div className="app-shell">
      <aside className="sidebar glass">
        <div className="brand">
          <span className="brand-dot" />
          <div>
            <strong>MMQP</strong>
            <p>Quant Research</p>
          </div>
        </div>
        <nav>
          {NAVIGATION.map((page) => (
            <button
              key={page.id}
              type="button"
              className={
                page.id === activePageId ? "nav-item active" : "nav-item"
              }
              aria-current={page.id === activePageId ? "page" : undefined}
              data-page={page.id}
              onClick={() => setActivePageId(page.id)}
            >
              {page.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span
            className={
              socialData.startsWith("Online") ? "online-dot" : "offline-dot"
            }
          />
          {socialData}
        </div>
      </aside>

      <main className="content">
        <header>
          <div>
            <p className="eyebrow">{activeNavigation.subtitle}</p>
            <h1>{activeNavigation.title}</h1>
            <p className="header-description">{activeNavigation.description}</p>
          </div>
          <button
            className="ghost-button"
            onClick={() => void refresh()}
            disabled={submitting}
          >
            刷新
          </button>
        </header>

        {activePageId === "overview" && (
          <section className="overview-shelf">
            <h2 id="page-title-overview">平台状态</h2>
            <div className="stat-row">
              <article className="stat-card glass">
                <span>工作区</span>
                <strong>{status?.workspace_count ?? "—"}</strong>
                <small>本地封面的项目</small>
              </article>
              <article className="stat-card glass">
                <span>数据快照</span>
                <strong>pending</strong>
                <small>等待摄取层</small>
              </article>
              <article className="stat-card glass">
                <span>运行记录</span>
                <strong>pending</strong>
                <small>等待实验层</small>
              </article>
              <article className="stat-card glass">
                <span>Schema</span>
                <strong>{status?.schema_version ?? "—"}</strong>
                <small>
                  {status?.compatible_restore_schema_versions.join(", ") || "—"}
                </small>
              </article>
            </div>

            <div className="panel-grid">
              <section className="glass card">
                <div className="card-head">
                  <div>
                    <h2>新建工作区</h2>
                    <p>工作区使用本地 SQLite、不可变对象存储和内容清单。</p>
                  </div>
                </div>
                <div className="form-grid">
                  <label>
                    绝对路径
                    <input
                      value={path}
                      onChange={(event) => setPath(event.target.value)}
                      placeholder="/Users/you/MMQP/Research"
                    />
                  </label>
                  <label>
                    显示名称
                    <input
                      value={displayName}
                      onChange={(event) => setDisplayName(event.target.value)}
                      placeholder="多市场研究"
                    />
                  </label>
                  <button
                    className="primary-button"
                    onClick={() => void createWorkspace()}
                    disabled={submitting}
                  >
                    {submitting ? "创建中…" : "创建工作区"}
                  </button>
                </div>
                {error && <pre className="error-banner">{error}</pre>}
              </section>

              <section className="glass card">
                <div className="card-head">
                  <div>
                    <h2>已注册工作区</h2>
                    <p>当前只显示本地注册表记录。</p>
                  </div>
                </div>
                <div className="workspace-list">
                  {workspaces.map((workspace) => (
                    <div key={workspace.id} className="workspace-row">
                      <div>
                        <strong>{workspace.display_name}</strong>
                        <small>{workspace.path}</small>
                      </div>
                      <span>UID {workspace.bound_uid}</span>
                    </div>
                  ))}
                </div>
                {workspaces.length === 0 && (
                  <div className="workspace-empty">
                    <strong>暂无本地工作区</strong>
                    <p>输入绝对路径后创建；数据快照与运行记录会进入当前封面。</p>
                  </div>
                )}
              </section>

              <section className="glass card quick-start-card">
                <div className="card-head">
                  <div>
                    <h2>快速开始</h2>
                    <p>直接进入行情、数据或研究运行。</p>
                  </div>
                </div>
                <div className="quick-actions">
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => setActivePageId("quote")}
                  >
                    读取行情
                  </button>
                  <button
                    className="button muted"
                    type="button"
                    onClick={() => setActivePageId("data")}
                  >
                    查询数据
                  </button>
                  <button
                    className="button muted"
                    type="button"
                    onClick={() => setActivePageId("backtest")}
                  >
                    提交运行
                  </button>
                </div>
                <div className="quick-status">
                  <div>
                    <span>接入源</span>
                    <strong>{sources?.length ?? "—"}</strong>
                  </div>
                  <div>
                    <span>Schema</span>
                    <strong>{status?.schema_version ?? "—"}</strong>
                  </div>
                  <div>
                    <span>服务</span>
                    <strong>{socialData.startsWith("Online") ? "在线" : "离线"}</strong>
                  </div>
                </div>
              </section>
            </div>
          </section>
        )}

        {activePageId === "data" && (
          <div className="data-workspace">
            <aside className="data-controls glass">
              <div className="card-head">
                <h2>数据查询</h2>
                <p>
                  读取本地不可变数据快照，结果按 Canonical_Asset_ID、观察日期和版本排序。
                </p>
              </div>
              <form
                className="data-control"
                onSubmit={(event) => {
                  event.preventDefault();
                  void runQuery();
                }}
              >
                <label>
                  数据集
                  <select
                    value={datasetName}
                    onChange={(event) =>
                      setDatasetName(event.target.value as QueryDataset)
                    }
                  >
                    {DATASETS.map((dataset) => (
                      <option key={dataset} value={dataset}>
                        {dataset}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  过滤字段
                  <select
                    data-testid="query-field"
                    value={queryField}
                    onChange={(event) => {
                      if (event.target.value === "") {
                        setQueryValue("");
                      }
                      setQueryField(event.target.value);
                    }}
                  >
                    <option value="">不过滤</option>
                    {(FILTER_OPTIONS[datasetName] ?? []).map((field) => (
                      <option key={field} value={field}>
                        {field}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  过滤值
                  <input
                    value={queryValue}
                    onChange={(event) => setQueryValue(event.target.value)}
                    disabled={!queryField}
                  />
                </label>
                <button
                  className="primary-button"
                  data-testid="query-submit"
                  type="submit"
                >
                  查询
                </button>
              </form>
            </aside>
            <section
              className={`data-stage glass ${
                queryResult ? "data-stage-result" : "data-stage-empty"
              }`}
            >
              {queryResult ? (
                <>
                  <div className="query-summary">
                    <span>快照 {queryResult.snapshot_id}</span>
                    <span>
                      匹配 {queryResult.matching_count} · 返回{" "}
                      {queryResult.returned_count}
                    </span>
                    <span>
                      过滤 {queryResult.applied_filter_count} · 还有更多{" "}
                      {queryResult.additional_results ? "是" : "否"}
                    </span>
                  </div>
                  <div className="query-results">
                    {queryResult.rows.length > 0 && (
                      <table className="query-table">
                        <thead>
                          <tr>
                            {Object.keys(queryResult.rows[0]).map((column) => (
                              <th key={column}>{column}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {queryResult.rows.map((row, rowIndex) => (
                            <tr key={rowIndex}>
                              {Object.keys(
                                queryResult.rows[0],
                              ).map((column) => (
                                <td key={column}>
                                  <span className="query-cell">
                                    {typeof row[column] === "object" &&
                                    row[column] !== null
                                      ? JSON.stringify(row[column])
                                      : String(row[column] ?? "—")}
                                  </span>
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    {queryResult.rows.length === 0 && <p>没有匹配记录。</p>}
                  </div>
                </>
              ) : (
                <div className="query-empty">
                  <strong>选择数据集与过滤条件</strong>
                  <p>
                    点击查询后，右侧展示匹配记录和快照摘要，数据按 Canonical_Asset_ID、观察日期和版本排序。
                  </p>
                </div>
              )}
              {queryError && <pre className="error-banner">{queryError}</pre>}
            </section>
          </div>
        )}

        {activePageId === "quote" && (
          <div className="quote-workspace">
            <aside className="quote-commands glass">
              <div className="quote-command-head">
                <strong>行情终端</strong>
                <small>选中数据源后自动读取真实日线</small>
              </div>
              <section className="stock-picker" aria-label="股票选择">
                <div className="stock-picker-head">
                  <strong>股票列表</strong>
                  <span data-testid="stock-loading">
                    {stockLoading ? "加载中" : `${stockChoices.length} 只`}
                  </span>
                </div>
                <input
                  data-testid="stock-search"
                  className="stock-search"
                  type="search"
                  placeholder="搜索代码或名称"
                  value={stockSearch}
                  onChange={(event) => setStockSearch(event.target.value)}
                />
                {stockError && <pre className="error-banner">{stockError}</pre>}
                <div className="stock-options" data-testid="stock-options">
                  {stockChoices.map((choice) => (
                    <button
                      data-testid="stock-option"
                      className={choice.symbol === symbol ? "active" : ""}
                      type="button"
                      key={choice.symbol}
                      onClick={() => chooseStock(choice)}
                    >
                      <strong>{choice.symbol}</strong>
                      <span>{choice.name}</span>
                      <small>{choice.currency}</small>
                    </button>
                  ))}
                  {!stockLoading && !stockChoices.length && (
                    <div className="stock-empty">
                      <strong>没有匹配股票</strong>
                      <p>调整关键词后继续搜索。</p>
                    </div>
                  )}
                </div>
              </section>
              <form
                className="quote-control"
                onSubmit={(event) => {
                  event.preventDefault();
                  void readSourceQuote();
                }}
              >
                <label>
                  数据源
                  <select
                    data-testid="quote-source-select"
                    value={activeSourceId}
                    onChange={(event) => {
                      const source = sources?.find(
                        (item) => item.id === event.target.value,
                      );
                      if (source) {
                        setSourceFocus(source);
                      }
                    }}
                  >
                    {sources
                      ?.filter((source) => source.category === "market")
                      .map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.display_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  市场
                  <select
                    data-testid="quote-market-select"
                    value={selectedMarketId}
                  onChange={(event) => {
                    const value = event.target.value;
                    setQuote(null);
                    setQuoteError(null);
                    setSelectedMarketId(value);
                      setSymbol(defaultMarketSymbol(value));
                      setQuote(null);
                      setQuoteError(null);
                    }}
                  >
                    {MARKET_OPTIONS.map((market) => (
                      <option key={market.id} value={market.id}>
                        {market.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  标的代码
                  <input
                    data-testid="quote-symbol"
                    type="text"
                    value={symbol}
                    onChange={(event) => setSymbol(event.target.value)}
                    placeholder="600000.SS"
                  />
                </label>
                <label>
                  行情日
                  <input
                    data-testid="quote-date"
                    type="date"
                    value={quoteDate}
                    onChange={(event) => setQuoteDate(event.target.value)}
                  />
                </label>
                <button
                  className="primary-button"
                  data-testid="quote-submit"
                  type="submit"
                  disabled={!sources || quoteLoading}
                >
                  {quoteLoading ? "读取中…" : "重新读取"}
                </button>
              </form>
              <div className="quote-provider">
                <span>当前供给</span>
                <strong>{activeSource?.display_name ?? "—"}</strong>
                {activeSource && <small>{activeSource.note}</small>}
              </div>
            </aside>
            <section className="quote-stage glass">
              <div className="quote-stage-head">
                <div>
                  <span>{activeMarket.label} · {activeMarket.exchange}</span>
                  <strong>{symbol}</strong>
                </div>
                <div className="quote-state">
                  {quoteLoading
                    ? "连接中"
                    : quote
                      ? "已加载"
                      : quoteError
                        ? "连接失败"
                        : "等待连接"}
                </div>
              </div>
                  {quoteError && <pre className="error-banner">{quoteError}</pre>}
                  {quoteError && (activeSource?.usage.required_env.length ?? 0) > 0 && (
                    <div className="quote-note">
                      <strong>缺少配置</strong>
                      <span>
                        {activeSource?.usage.required_env.join(" · ")}
                      </span>
                    </div>
                  )}
                  {quoteFallback && (
                    <div className="quote-note">
                      <strong>行情回退</strong>
                      <span>已使用 Yahoo Finance 提供快照。</span>
                    </div>
                  )}
                  {quote ? (
                <div className="quote-stage-body" data-testid="quote-result">
                  <div className="quote-hero">
                    <div>
                      <span>{quote.trading_date} 收盘价</span>
                      <strong>{quoteNumber(quote.close)}</strong>
                      <small>{quote.trading_currency}</small>
                    </div>
                    <div>
                      <span>开盘价差</span>
                      <strong>
                        {(
                          ((Number(quote.close) - Number(quote.open)) /
                            Number(quote.open)) *
                          100
                        ).toFixed(2)}
                        %
                      </strong>
                      <small>{quote.provider}</small>
                    </div>
                  </div>
                  {quote.trading_date !== quoteDate && (
                    <div className="quote-note">
                      <strong>已自动回退</strong>
                      <span>{quote.trading_date} · 开盘价差仍按当日开盘计算。</span>
                    </div>
                  )}
                  <dl className="quote-metrics">
                    <div>
                      <dt>开盘</dt>
                      <dd>{quoteNumber(quote.open)}</dd>
                    </div>
                    <div>
                      <dt>最高</dt>
                      <dd>{quoteNumber(quote.high)}</dd>
                    </div>
                    <div>
                      <dt>最低</dt>
                      <dd>{quoteNumber(quote.low)}</dd>
                    </div>
                    <div>
                      <dt>成交量</dt>
                      <dd>{quoteNumber(quote.volume)}</dd>
                    </div>
                    <div>
                      <dt>成交额</dt>
                      <dd>{quoteNumber(quote.turnover)}</dd>
                    </div>
                    <div>
                      <dt>数据源</dt>
                      <dd>{quote.provider}</dd>
                    </div>
                  </dl>
                </div>
              ) : (
                <div className={`quote-empty ${quoteError ? "failed" : ""}`}>
                  <strong>
                    {quoteLoading
                      ? "正在连接数据源"
                      : quoteError
                        ? "连接失败"
                        : "等待真实行情"}
                  </strong>
                  <p>
                    点击数据源卡片后，这里会直接加载所选供给的单日 OHLCV，不需要手动提交 POST。
                  </p>
                </div>
              )}
              <section className="quote-history glass">
                <div className="quote-history-head">
                  <div>
                    <span>历史 K线</span>
                    <strong>{quoteHistory ? `${quoteHistory.length} 个交易日` : "日线"}</strong>
                  </div>
                  <div className="history-periods">
                    <button
                      data-testid="history-period-5d"
                      className="history-period"
                      type="button"
                      onClick={() => void readSourceHistory(5)}
                    >
                      5D
                    </button>
                    <button
                      data-testid="history-period-30d"
                      className="history-period"
                      type="button"
                      onClick={() => void readSourceHistory(30)}
                    >
                      30D
                    </button>
                    <button
                      data-testid="history-period-60d"
                      className="history-period"
                      type="button"
                      onClick={() => void readSourceHistory(60)}
                    >
                      60D
                    </button>
                    <button
                      data-testid="history-period-120d"
                      className="history-period"
                      type="button"
                      onClick={() => void readSourceHistory(120)}
                    >
                      120D
                    </button>
                  </div>
                  <button className="primary-button" type="button" onClick={() => void readSourceHistory(5)}>
                    读取 K线
                  </button>
                </div>
                {historyError && <pre className="error-banner">{historyError}</pre>}
                {historyError && (activeSource?.usage.required_env.length ?? 0) > 0 && (
                  <div className="quote-note">
                    <strong>缺少配置</strong>
                    <span>{activeSource?.usage.required_env.join(" · ")}</span>
                  </div>
                )}
                {historyFallback && (
                  <div className="quote-note">
                    <strong>历史回退</strong>
                    <span>已使用 Yahoo Finance 提供所选窗口。</span>
                  </div>
                )}
                {quoteHistory && quoteHistory.length > 0 ? (
                  <div className="quote-history-grid">
                    {quoteHistory.map((bar) => (
                      <article className="history-bar" key={bar.trading_date}>
                        <div className="history-bar-head">
                          <span>{bar.trading_date}</span>
                          <strong>{quoteNumber(bar.close)}</strong>
                        </div>
                        <dl className="history-facts">
                          <div>
                            <dt>开</dt>
                            <dd>{quoteNumber(bar.open)}</dd>
                          </div>
                          <div>
                            <dt>高</dt>
                            <dd>{quoteNumber(bar.high)}</dd>
                          </div>
                          <div>
                            <dt>低</dt>
                            <dd>{quoteNumber(bar.low)}</dd>
                          </div>
                          <div>
                            <dt>量</dt>
                            <dd>{quoteNumber(bar.volume)}</dd>
                          </div>
                        </dl>
                        <small>
                          {bar.provider} · {bar.trading_currency}
                        </small>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className={`quote-history-empty ${historyError ? "failed" : ""}`}>
                    <strong>{historyLoading ? "正在读取历史" : "暂无历史数据"}</strong>
                    <p>点击上方周期按钮，读取所选数据源的历史日线。</p>
                  </div>
                )}
              </section>
            </section>
          </div>
        )}

        {activePageId === "sources" && (
          <section className="glass card source-shelf">
            <div className="card-head">
              <h2>目录与接入状态</h2>
              <p>
                内置免费/本地研究源目录；点击行情源卡片进入独立行情快照页。
              </p>
              <p className="source-footnote">
                已接入 {sources?.filter(
                  (source) => source.implementation_status === "connected",
                ).length ?? 0}{" "}
                个。仅目录 {sources?.filter(
                  (source) => source.implementation_status === "cataloged",
                ).length ?? 0}{" "}
                个仅目录。
              </p>
            </div>
            {activeSource && (
              <section className="source-detail">
                <div className="detail-head">
                  <div>
                    <span>{activeSource.category}</span>
                    <strong>{activeSource.display_name}</strong>
                  </div>
                  <small>
                    {activeSource.scope} · {activeSource.frequency} ·{" "}
                    {activeSource.provider}
                  </small>
                  <p>{activeSource.note}</p>
                </div>
                <dl className="detail-grid">
                  <div>
                    <dt>报价能力</dt>
                    <dd>
                      {activeSource.category === "market"
                        ? "单日开盘行情快照"
                        : "目录与后续摄取能力"}
                    </dd>
                  </div>
                  <div>
                    <dt>数据范围</dt>
                    <dd>
                    <ul>
                      {activeSource.usage.request_fields.map((field) => (
                        <li key={field.name}>{field.label}</li>
                      ))}
                    </ul>
                    </dd>
                  </div>
                  <div>
                    <dt>所需环境变量</dt>
                    <dd>
                      {activeSource.usage.required_env.length
                        ? activeSource.usage.required_env.join(" · ")
                        : "无"}
                    </dd>
                  </div>
                </dl>
              </section>
            )}
            <div className="source-grid">
              {sources?.map((source) => (
                <article
                  key={source.id}
                  data-testid="source-card"
                  className={
                    activeSource?.id === source.id
                      ? "source-card glass active"
                      : "source-card glass"
                  }
                  onClick={() => setSourceFocus(source)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSourceFocus(source);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <div className="source-title">
                    <span>{source.category}</span>
                    <strong>{source.display_name}</strong>
                  </div>
                  <small>{source.note}</small>
                  <div className="source-usage">
                    <span className="usage-route">
                      {source.usage.method} {source.usage.endpoint}
                    </span>
                    <span className="usage-fields">
                      {source.usage.request_fields
                        .map((field) => field.label)
                        .join(" · ")}
                    </span>
                    {source.usage.required_env.length > 0 && (
                      <span className="usage-env">
                        {source.usage.required_env.join(" · ")}
                      </span>
                    )}
                  </div>
                  <div className="source-meta">
                    <span>{source.scope}</span>
                    <span
                      className={
                        source.implementation_status === "connected"
                          ? "source-connected"
                          : "source-cataloged"
                      }
                    >
                      {source.implementation_status === "connected"
                        ? "已接入"
                        : "未接入"}
                    </span>
                    <span>{source.requires_auth ? "需授权" : "公开"}</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {activePageId === "backtest" && (
          <section id="research-runs" className="glass card run-shelf">
            <div className="card-head">
              <h2>参数与引用</h2>
              <p>
                提交研究窗口与全部引用版本；当前仅生成仿真模拟回执，不会发送真实订单。
              </p>
            </div>
            <div className="run-body">
              <form className="run-form"
              onSubmit={(event) => {
                event.preventDefault();
                void submitRun();
              }}
            >
              <label>
                开始日期
                <input
                  type="date"
                  value={runWindowStart}
                  onChange={(event) => setRunWindowStart(event.target.value)}
                />
              </label>
              <label>
                结束日期
                <input
                  type="date"
                  value={runWindowEnd}
                  onChange={(event) => setRunWindowEnd(event.target.value)}
                />
              </label>
              <div className="quote-source">
                <span>分析行情源</span>
                <strong>{activeSource?.display_name ?? "未选择"}</strong>
              </div>
              <label>
                基准货币
                <input
                  value={runBaseCurrency}
                  onChange={(event) => setRunBaseCurrency(event.target.value)}
                  maxLength={3}
                />
              </label>
              {RUN_FIELD_LABELS.map(({ key, label }) => (
                <label key={key}>
                  {label}
                  <input
                    value={runVersions[key]}
                    onChange={(event) =>
                      setRunVersions((previous) => ({
                        ...previous,
                        [key]: event.target.value,
                      }))
                    }
                    placeholder="版本 ID"
                  />
                </label>
              ))}
              <button
                className="primary-button"
                data-testid="run-submit"
                type="submit"
                disabled={runSubmitting}
              >
                {runSubmitting ? "提交中…" : "提交研究"}
              </button>
            </form>
            <div className={`run-receipt ${runReceipt ? "" : "pending"}`}>
              <span>
                {runReceipt?.run_created
                  ? "运行已创建"
                  : runReceipt
                    ? "模拟回执"
                    : "模拟回执"}
              </span>
              <span>
                {runReceipt ? `快照 ${runReceipt.snapshot_id}` : "尚未提交"}
              </span>
              <small>
                {runReceipt?.disclaimer ??
                  "提交窗口与版本后生成仿真回执，不发送真实订单。"}
              </small>
            </div>
            {runError && <pre className="error-banner">{runError}</pre>}
            </div>
          </section>
        )}

        {activePageId === "factor" && (
          <section id="market-calendars" className="glass card market-shelf">
            <div className="card-head">
              <div>
              <h2>买盘校验</h2>
                <p>
                  查询交易/估值日历，并按当前基准评估买盘的 lot、tick、可用性和
                  T+n 结算时钟。
                </p>
              </div>
            </div>
            <div className="market-body">
            <div className="market-query">
              <label>
                市场
                <select
                  data-testid="market-select"
                  value={selectedMarketId}
                  onChange={(event) => setSelectedMarketId(event.target.value)}
                >
                  {MARKET_OPTIONS.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                生效日
                <input
                  type="date"
                  value={effectiveDate}
                  onChange={(event) => setEffectiveDate(event.target.value)}
                />
              </label>
              <label>
                数量
                <input
                  value={orderQuantity}
                  onChange={(event) => setOrderQuantity(event.target.value)}
                />
              </label>
              <label>
                价格
                <input
                  value={orderPrice}
                  onChange={(event) => setOrderPrice(event.target.value)}
                />
              </label>
              <label>
                {selectedMarketId === "a-share" ? "涨跌幅" : "价格带"}
                <input
                  value={referencePrice}
                  onChange={(event) => setReferencePrice(event.target.value)}
                />
              </label>
              <button
                className="primary-button"
                onClick={() => void evaluate()}
              >
                评估买盘
              </button>
            </div>

            {tradingCalendar && valuationCalendar && (
              <div className="rule-grid">
                <div className="metric">
                  <span>交易历</span>
                  <strong>{tradingCalendar.version_id}</strong>
                  <small>
                    {tradingCalendar.exchange} · {tradingCalendar.timezone}
                  </small>
                </div>
                <div className="metric">
                  <span>估值历</span>
                  <strong>{valuationCalendar.version_id}</strong>
                  <small>{valuationCalendar.timezone}</small>
                </div>
                <div className="metric">
                  <span>记录日数</span>
                  <strong>{tradingCalendar.days.length}</strong>
                  <small>成交日 / 休息日 / 半日</small>
                </div>
                <div className="metric">
                  <span>生效范围</span>
                  <strong>
                    {tradingCalendar.effective_from.slice(0, 4)} ·{" "}
                    {tradingCalendar.effective_to?.slice(0, 4) ?? "—"}
                  </strong>
                  <small>年度日历版本</small>
                </div>
              </div>
            )}

            {marketRule && (
              <div className="rule-grid">
                <div className="metric">
                  <span>规则版本</span>
                  <strong>{marketRule.version_id}</strong>
                  <small>{marketRule.asset_type}</small>
                </div>
                <div className="metric">
                  <span>最小手数 / 目标价</span>
                  <strong>{marketRule.trading_lot}</strong>
                  <small>{marketRule.tick_size}</small>
                </div>
                <div className="metric">
                  <span>限价 / 价格带</span>
                  <strong>{Number(orderPrice).toFixed(2)}</strong>
                  <small>
                    {marketRule.price_limit_percent ?? "按供应商价格带"}
                  </small>
                </div>
                <div className="metric">
                  <span>可用 / 结算</span>
                  <strong>{marketRule.sell_availability_rule}</strong>
                  <small>T+{marketRule.security_settlement_open_dates}</small>
                </div>
              </div>
            )}

            {evaluation && (
              <div className="rule-grid">
                <div className="metric">
                  <span>可成交数量</span>
                  <strong>{evaluation.filled_quantity}</strong>
                  <small>有效数量 {evaluation.valid_quantity}</small>
                </div>
                <div className="metric">
                  <span>有效价格</span>
                  <strong>{evaluation.valid_price ?? "—"}</strong>
                  <small>
                    来源 {evaluation.rule_source_version_id ?? "无"}
                  </small>
                </div>
                <div className="metric">
                  <span>卖出可用日</span>
                  <strong>{evaluation.sell_available_date ?? "—"}</strong>
                  <small>
                    清算 {evaluation.security_settlement_date ?? "—"}
                  </small>
                </div>
                <div className="metric">
                  <span>状态</span>
                  <strong>
                    {evaluation.rejection_reason ? "拒绝" : "通过"}
                  </strong>
                  <small>{evaluation.rejection_reason ?? "规则校验完成"}</small>
                </div>
              </div>
            )}

            {marketError && <pre className="error-banner">{marketError}</pre>}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
