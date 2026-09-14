export interface Workspace {
  id: string;
  path: string;
  display_name: string;
  bound_uid: number;
  created_at: string | null;
}

export interface PlatformStatus {
  platform_version: string;
  workspace_count: number;
  schema_version: number;
  compatible_restore_schema_versions: number[];
}

export interface DataSource {
  id: string;
  provider: string;
  display_name: string;
  category: "market" | "fundamental" | "corporate_action" | "macro" | "calendar";
  scope: "A_SHARE" | "HONG_KONG" | "UNITED_STATES" | "GLOBAL";
  frequency: "daily" | "event" | "reference" | "monthly" | "quarterly";
  implementation_status: "cataloged" | "connected";
  requires_auth: boolean;
  documentation_url: string;
  note: string;
  usage: {
    endpoint: string;
    method: "POST";
    request_fields: {
      name: string;
      label: string;
      value_type: "string" | "integer" | "date";
      required: boolean;
      description: string;
    }[];
    required_env: string[];
  };
}

export type SourceTicker = {
  id: string;
  symbol: string;
  marketId: string;
  open: string;
  close: string;
  volume: string;
  time: string;
};

export interface AssetIdentity {
  market: string;
  asset_type: string;
  exchange: string;
  local_code: string;
}

export interface AssetVersion {
  version_id: string;
  asset_id: string;
  identity: AssetIdentity;
  name: string;
  trading_currency: string;
  lifecycle_status: string;
  effective_from: string;
  effective_to: string | null;
  predecessor_id: string | null;
}

export interface ProviderAssetMapping {
  provider: string;
  provider_code: string;
  asset_id: string;
  effective_from: string;
  effective_to: string | null;
  mapping_id: string;
}

export type CalendarDayKind = "closed" | "full" | "half";
export type SessionKind = "regular" | "non_regular";

export interface TradingSession {
  start: string;
  end: string;
  kind: SessionKind;
}

export interface TradingCalendarDay {
  market: string;
  exchange: string;
  date: string;
  kind: CalendarDayKind;
  sessions: TradingSession[];
}

export interface TradingCalendarVersion {
  version_id: string;
  market: string;
  exchange: string;
  timezone: string;
  effective_from: string;
  effective_to: string | null;
  days: TradingCalendarDay[];
}

export interface ValuationCalendarVersion {
  version_id: string;
  market: string;
  timezone: string;
  effective_from: string;
  effective_to: string | null;
}

export interface MarketRuleProfile {
  version_id: string;
  market: string;
  exchange: string;
  asset_type: string;
  effective_from: string;
  effective_to: string | null;
  trading_lot: number;
  tick_size: string;
  price_limit_rule: string;
  price_limit_percent: string | null;
  sell_availability_rule: string;
  security_settlement_open_dates: number;
  cash_settlement_open_dates: number;
  permitted_session_types: SessionKind[];
}

export interface EvaluatedTrade {
  filled_quantity: string;
  valid_quantity: string | null;
  valid_price: string | null;
  sell_available_date: string | null;
  security_settlement_date: string | null;
  cash_settlement_date: string | null;
  rejection_reason: string | null;
  rule_source_version_id: string | null;
  matches: string[];
}

export type FilterValue = string | number | null;

export interface QueryFilter {
  field: string;
  values: FilterValue[];
}

export type QueryDataset =
  | "ASSET_MASTER"
  | "DAILY_BAR"
  | "FUND_NAV"
  | "FUNDAMENTAL_FACT"
  | "TRADING_CALENDAR"
  | "MARKET_RULE_PROFILE"
  | "VALUATION_CALENDAR"
  | "CORPORATE_ACTION";

export interface QueryRequest {
  dataset: QueryDataset;
  filters: QueryFilter[];
}

export interface QueryResult {
  snapshot_id: string;
  query: {
    dataset: QueryDataset;
    filters: QueryFilter[];
    limit: number;
    offset: number;
  };
  matching_count: number;
  returned_count: number;
  applied_filter_count: number;
  additional_results: boolean;
  rows: Record<string, unknown>[];
}

export interface ResearchRunRequest {
  snapshot_id: string;
  start_date: string;
  end_date: string;
  base_currency: string;
  factor_definition_version: string;
  universe_version: string;
  portfolio_definition_version: string;
  strategy_version: string;
  transaction_cost_model_version: string;
  risk_model_version: string;
}

export interface RunSubmissionReceipt {
  snapshot_id: string;
  request: Record<string, unknown>;
  result_kind: string;
  disclaimer: string;
  run_created: boolean;
  run_id?: string;
  manifest_id?: string;
}
