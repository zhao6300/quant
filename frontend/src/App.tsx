import { useCallback, useEffect, useState } from "react";
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
} from "./types";

const client = new ApiClient();

const MARKET_OPTIONS = [
  { id: "a-share", label: "A股", market: "A_SHARE", exchange: "SSE" },
  { id: "hong-kong", label: "港股", market: "HONG_KONG", exchange: "HKEX" },
  { id: "united-states", label: "美股", market: "UNITED_STATES", exchange: "NYSE" },
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
  CORPORATE_ACTION: ["version_id", "canonical_asset_id", "event_id", "action_type", "provenance_id"],
};

type RunVersionFields = Omit<ResearchRunRequest, "snapshot_id" | "start_date" | "end_date" | "base_currency">;

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
] as const;

type NavigationId = (typeof NAVIGATION)[number]["id"];

function marketById(id: string): MarketOption {
  return MARKET_OPTIONS.find((option) => option.id === id) ?? MARKET_OPTIONS[0];
}

function App() {
  const [socialData, setSocialData] = useState("Loading");
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [sources, setSources] = useState<DataSource[] | null>(null);
  const [tradingCalendar, setTradingCalendar] = useState<TradingCalendarVersion | null>(null);
  const [valuationCalendar, setValuationCalendar] = useState<ValuationCalendarVersion | null>(null);
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
  const [runReceipt, setRunReceipt] = useState<RunSubmissionReceipt | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [runSubmitting, setRunSubmitting] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [activePageId, setActivePageId] = useState<NavigationId>("overview");

  const activeMarket = marketById(selectedMarketId);
  const activeNavigation = NAVIGATION.find((page) => page.id === activePageId) ?? NAVIGATION[0];

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
      })
    );
  }, [activeMarket.exchange, activeMarket.market, effectiveDate, orderPrice, orderQuantity, referencePrice]);

  const refresh = useCallback(async () => {
    try {
      const [fetchedStatus, fetchedWorkspaces, fetchedSources] = await Promise.all([
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
        filters: queryValue ? [{ field: queryField, values: [queryValue] }] : [],
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
        client.tradingCalendar(activeMarket.market, activeMarket.exchange, requestedDate),
        client.valuationCalendar(activeMarket.market, requestedDate),
      ]);
      setTradingCalendar(calendar);
      setValuationCalendar(valuation);
      try {
        setMarketRule(await client.marketRule(activeMarket.market, activeMarket.exchange, "EQUITY", requestedDate));
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
      await client.createWorkspace(path.trim(), displayName.trim() || undefined);
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
              className={page.id === activePageId ? "nav-item active" : "nav-item"}
              aria-current={page.id === activePageId ? "page" : undefined}
              onClick={() => setActivePageId(page.id)}
            >
              {page.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className={socialData.startsWith("Online") ? "online-dot" : "offline-dot"} />
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
          <button className="ghost-button" onClick={() => void refresh()} disabled={submitting}>
            刷新
          </button>
        </header>

        {activePageId === "overview" && <section className="stat-row">
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
            <small>{status?.compatible_restore_schema_versions.join(", ") || "—"}</small>
          </article>
        </section>}

      {activePageId === "overview" && <div className="panel-grid">
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
                <input value={path} onChange={(event) => setPath(event.target.value)} placeholder="/Users/you/MMQP/Research" />
              </label>
              <label>
                显示名称
                <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="多市场研究" />
              </label>
              <button className="primary-button" onClick={() => void createWorkspace()} disabled={submitting}>
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
    </section>
        </div>}

        {activePageId === "data" && <section className="glass card">
          <div className="card-head">
            <h2>数据查询</h2>
            <p>读取本地不可变数据快照，结果按 Canonical_Asset_ID、观察日期和版本排序。</p>
          </div>
          <form className="query-form" onSubmit={(event) => {
            event.preventDefault();
            void runQuery();
          }}>
            <label>
              数据集
              <select value={datasetName} onChange={(event) => setDatasetName(event.target.value as QueryDataset)}>
                {DATASETS.map((dataset) => (
                  <option key={dataset} value={dataset}>{dataset}</option>
                ))}
              </select>
            </label>
            <label>
              过滤字段
              <select value={queryField} onChange={(event) => {
                if (event.target.value === "") {
                  setQueryValue("");
                }
                setQueryField(event.target.value);
              }}>
                <option value="">不过滤</option>
                {(FILTER_OPTIONS[datasetName] ?? []).map((field) => (
                  <option key={field} value={field}>{field}</option>
                ))}
              </select>
            </label>
            <label>
              过滤值
              <input value={queryValue} onChange={(event) => setQueryValue(event.target.value)} disabled={!queryField} />
            </label>
            <button className="primary-button" type="submit">查询</button>
          </form>
          {queryResult && (
            <div className="query-summary">
              <span>快照 {queryResult.snapshot_id}</span>
              <span>匹配 {queryResult.matching_count} · 返回 {queryResult.returned_count}</span>
              <span>过滤 {queryResult.applied_filter_count} · 还有更多 {queryResult.additional_results ? "是" : "否"}</span>
            </div>
          )}
          {queryResult && (
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
                        {Object.keys(queryResult.rows[0]).map((column) => (
                          <td key={column}>
                            <span className="query-cell">
                              {typeof row[column] === "object" && row[column] !== null
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
          )}
          {queryError && <pre className="error-banner">{queryError}</pre>}
        </section>}

        {activePageId === "sources" && (
          <section className="glass card source-shelf">
            <div className="card-head">
              <h2>外部数据源</h2>
              <p>内置数据源目录，包含免费行情、基本面、公告、宏观与交易日历源；当前展示接入规划，尚未执行实际取数。</p>
            </div>
            <div className="source-grid">
              {sources?.map((source) => (
                <article key={source.id} className="source-card glass">
                  <div>
                    <span>{source.category}</span>
                    <strong>{source.display_name}</strong>
                  </div>
                  <small>{source.note}</small>
                  <div className="source-meta">
                    <span>{source.scope}</span>
                    <span className={source.implementation_status === "connected" ? "source-connected" : "source-cataloged"}>
                      {source.implementation_status === "connected" ? "已接入" : "未接入"}
                    </span>
                    <span>{source.requires_auth ? "需授权" : "公开"}</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {activePageId === "backtest" && <section
          id="research-runs"
          className="glass card"
        >
          <div className="card-head">
            <h2>研究运行</h2>
            <p>提交研究窗口与全部引用版本；当前仅生成仿真模拟回执，不会发送真实订单。</p>
          </div>
          <form
            className="run-form"
            onSubmit={(event) => {
              event.preventDefault();
              void submitRun();
            }}
          >
            <label>
              开始日期
              <input type="date" value={runWindowStart} onChange={(event) => setRunWindowStart(event.target.value)} />
            </label>
            <label>
              结束日期
              <input type="date" value={runWindowEnd} onChange={(event) => setRunWindowEnd(event.target.value)} />
            </label>
            <label>
              基准货币
              <input value={runBaseCurrency} onChange={(event) => setRunBaseCurrency(event.target.value)} maxLength={3} />
            </label>
            {RUN_FIELD_LABELS.map(({ key, label }) => (
              <label key={key}>
                {label}
                <input value={runVersions[key]} onChange={(event) => setRunVersions((previous) => ({ ...previous, [key]: event.target.value }))} placeholder="版本 ID" />
              </label>
            ))}
            <button className="primary-button" type="submit" disabled={runSubmitting}>
              {runSubmitting ? "提交中…" : "提交研究"}
            </button>
          </form>
          {runReceipt && (
            <div className="run-receipt">
              <span>{runReceipt.run_created ? "运行已创建" : "模拟回执"}</span>
              <span>快照 {runReceipt.snapshot_id}</span>
              <small>{runReceipt.disclaimer}</small>
            </div>
          )}
          {runError && <pre className="error-banner">{runError}</pre>}
        </section>}

        {activePageId === "factor" && <section
          id="market-calendars"
          className="glass card market-shelf"
        >
          <div className="card-head">
            <div>
              <h2>多市场日历与规则</h2>
              <p>查询交易/估值日历，并按当前基准评估买盘的 lot、tick、可用性和 T+n 结算时钟。</p>
            </div>
          </div>

          <div className="market-query">
            <label>
              市场
              <select
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
              <input value={orderPrice} onChange={(event) => setOrderPrice(event.target.value)} />
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
                <small>{tradingCalendar.exchange} · {tradingCalendar.timezone}</small>
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
                <strong>{(Number(orderPrice)).toFixed(2)}</strong>
                <small>{marketRule.price_limit_percent ?? "按供应商价格带"}</small>
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
                <small>来源 {evaluation.rule_source_version_id ?? "无"}</small>
              </div>
              <div className="metric">
                <span>卖出可用日</span>
                <strong>{evaluation.sell_available_date ?? "—"}</strong>
                <small>清算 {evaluation.security_settlement_date ?? "—"}</small>
              </div>
              <div className="metric">
                <span>状态</span>
                <strong>{evaluation.rejection_reason ? "拒绝" : "通过"}</strong>
                <small>{evaluation.rejection_reason ?? "规则校验完成"}</small>
              </div>
            </div>
          )}

          {marketError && <pre className="error-banner">{marketError}</pre>}
        </section>}
      </main>
    </div>
  );
}

export default App;
