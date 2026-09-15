import type {
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
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiClient {
  constructor(private readonly baseUrl: string = API_BASE_URL) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `${response.status} ${response.statusText}`);
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
    },
  ): Promise<SourceHistory> {
    const query = new URLSearchParams(payload);
    return this.request<SourceHistory>(
      `/api/v1/data-sources/${sourceId}/history?${query}`,
    );
  }

  workspaces(): Promise<Workspace[]> {
    return this.request<Workspace[]>("/api/v1/workspaces");
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
      body: JSON.stringify({ ...request, limit: 100, offset: 0 }),
    });
  }

  createWorkspace(path: string, displayName?: string): Promise<Workspace> {
    return this.request<Workspace>("/api/v1/workspaces", {
      method: "POST",
      body: JSON.stringify({ path, display_name: displayName || undefined }),
    });
  }
}
