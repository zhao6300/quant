import type {
  AssistantContextPayload,
  AssistantMode,
  AssistantResponse,
  EvaluatedTrade,
  AssetVersion,
  MarketRuleProfile,
  ProviderAssetMapping,
  PlatformStatus,
  DataSource,
  QueryRequest,
  QueryResult,
  ResearchRunRequest,
  RunSubmissionReceipt,
  TradingCalendarVersion,
  ValuationCalendarVersion,
  Workspace,
  SourceTicker,
  SourceHistory,
  StockChoices,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiClient {
  constructor(private readonly baseUrl: string = API_BASE_URL) {}

  private apiErrorMessage(response: Response, rawMessage: string): string {
    try {
      const payload = JSON.parse(rawMessage) as Record<string, unknown>;
      if (typeof payload.detail === "string") return payload.detail;
      if (Array.isArray(payload.detail)) {
        const details = payload.detail.map((item) => {
          const detail = item as {
            field?: unknown;
            message?: unknown;
            loc?: unknown;
          };
          const path = Array.isArray(detail.loc)
            ? detail.loc.filter((node) => node !== "body")
            : [];
          const field =
            detail.field ?? (path.length ? String(path[path.length - 1]) : "");
          return field && typeof detail.message === "string"
            ? `${field}: ${detail.message}`
            : "提交字段校验失败";
        });
        return details.filter(Boolean).join("；") || "提交字段校验失败";
      }
      if (payload.status === 400 && typeof payload.title === "string") {
        const fields = payload.fields as Record<string, unknown> | undefined;
        const dependent = fields?.provider;
        return dependent && Array.isArray(dependent)
          ? `数据源暂时不可用：${dependent.join("、")}`
          : payload.title;
      }
    } catch {}
    return rawMessage || `${response.status} ${response.statusText}`;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(this.apiErrorMessage(response, message));
    }

    return (await response.json()) as T;
  }

  submitRun(request: ResearchRunRequest): Promise<RunSubmissionReceipt> {
    return this.request("/api/v1/runs", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  status(): Promise<PlatformStatus> {
    return this.request<PlatformStatus>("/api/v1/status");
  }

  dataSources(): Promise<DataSource[]> {
    return this.request<DataSource[]>("/api/v1/data-sources");
  }

  sourceQuote(
    sourceId: string,
    payload: {
      market: string;
      exchange: string;
      symbol: string;
      trading_date: string;
    },
  ): Promise<SourceTicker> {
    const query = new URLSearchParams(payload);
    return this.request<SourceTicker>(
      `/api/v1/data-sources/${sourceId}/quote?${query}`,
    );
  }

  sourceHistory(
    sourceId: string,
    payload: {
      market: string;
      exchange: string;
      symbol: string;
      trading_date: string;
      limit: string;
    },
  ): Promise<SourceHistory> {
    const query = new URLSearchParams(payload);
    return this.request<SourceHistory>(
      `/api/v1/data-sources/${sourceId}/history?${query}`,
    );
  }

  stockChoices(market: string, query: string = ""): Promise<StockChoices> {
    const querystring = new URLSearchParams({ market, query });
    return this.request<StockChoices>(`/api/v1/stocks?${querystring}`);
  }

  workspaces(): Promise<Workspace[]> {
    return this.request<Workspace[]>("/api/v1/workspaces");
  }

  assistantRespond(payload: {
    message: string;
    context: AssistantContextPayload;
    mode: AssistantMode;
  }): Promise<AssistantResponse> {
    return this.request<AssistantResponse>("/api/v1/assistant/respond", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  registerAsset(asset: {
    market: string;
    asset_type: string;
    exchange: string;
    local_code: string;
    name: string;
    trading_currency: string;
    lifecycle_status: string;
    effective_from: string;
    effective_to?: string | null;
  }): Promise<AssetVersion> {
    return this.request<AssetVersion>("/api/v1/assets", {
      method: "POST",
      body: JSON.stringify(asset),
    });
  }

  providerAssetMapping(mapping: {
    provider: string;
    provider_code: string;
    asset_id: string;
    effective_from: string;
    effective_to?: string | null;
  }): Promise<ProviderAssetMapping> {
    return this.request<ProviderAssetMapping>("/api/v1/assets/provider-mappings", {
      method: "POST",
      body: JSON.stringify(mapping),
    });
  }

  tradingCalendar(market: string, exchange: string, asOf: string): Promise<TradingCalendarVersion> {
    const query = new URLSearchParams({ market, exchange, as_of: asOf });
    return this.request<TradingCalendarVersion>(`/api/v1/calendars/trading?${query}`);
  }

  valuationCalendar(market: string, asOf: string): Promise<ValuationCalendarVersion> {
    const query = new URLSearchParams({ market, as_of: asOf });
    return this.request<ValuationCalendarVersion>(`/api/v1/calendars/valuation?${query}`);
  }

  marketRule(market: string, exchange: string, assetType: string, asOf: string): Promise<MarketRuleProfile> {
    const query = new URLSearchParams({ market, exchange, asset_type: assetType, as_of: asOf });
    return this.request<MarketRuleProfile>(`/api/v1/market-rules?${query}`);
  }

  evaluateTrade(request: {
    market: string;
    exchange: string;
    asset_type: string;
    trade_date: string;
    side: string;
    requested_quantity: string;
    requested_price: string;
    reference_price?: string;
    market_data_price_limit_percent?: string;
    market_data_price_band_percent?: string;
    sellable_quantity: string;
  }): Promise<EvaluatedTrade> {
    return this.request<EvaluatedTrade>("/api/v1/market-rules/evaluate", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  queryDataset(request: QueryRequest): Promise<QueryResult> {
    return this.request<QueryResult>("/api/v1/queries/results", {
      method: "POST",
      body: JSON.stringify({
        snapshot_id: "LIVE",
        dataset: request.dataset,
        filters: request.filters,
        limit: 100,
        offset: 0,
      }),
    });
  }

  createWorkspace(path: string, displayName?: string): Promise<Workspace> {
    return this.request<Workspace>("/api/v1/workspaces", {
      method: "POST",
      body: JSON.stringify({ path, display_name: displayName || undefined }),
    });
  }
}
