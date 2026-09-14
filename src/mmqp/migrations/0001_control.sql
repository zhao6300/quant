CREATE TABLE IF NOT EXISTS migration_history (
    migration_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS workspace (
    workspace_id TEXT PRIMARY KEY,
    canonical_path TEXT NOT NULL UNIQUE,
    bound_uid INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    format_version INTEGER NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS operation (
    operation_id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    bound_uid INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('started', 'committed', 'rolled_back')),
    intent_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    CHECK ((completed_at IS NULL AND status = 'started') OR (completed_at IS NOT NULL AND status <> 'started'))
) STRICT;

CREATE TABLE IF NOT EXISTS asset_identity (
    canonical_asset_id TEXT PRIMARY KEY,
    market TEXT NOT NULL,
    exchange TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    local_code TEXT NOT NULL,
    UNIQUE (market, exchange, asset_type, local_code)
) STRICT;

CREATE TABLE IF NOT EXISTS asset_master_version (
    asset_master_version_id TEXT PRIMARY KEY,
    canonical_asset_id TEXT NOT NULL REFERENCES asset_identity(canonical_asset_id),
    name TEXT NOT NULL,
    lifecycle_status TEXT NOT NULL,
    effective_start TEXT NOT NULL,
    effective_end TEXT NOT NULL,
    predecessor_version_id TEXT REFERENCES asset_master_version(asset_master_version_id),
    created_at TEXT NOT NULL,
    CHECK (effective_start <= effective_end),
    UNIQUE (canonical_asset_id, effective_start)
) STRICT;

CREATE INDEX IF NOT EXISTS asset_master_version_lookup
    ON asset_master_version(canonical_asset_id, effective_start, effective_end);

CREATE TABLE IF NOT EXISTS provider_asset_mapping (
    mapping_version_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_code TEXT NOT NULL,
    canonical_asset_id TEXT NOT NULL REFERENCES asset_identity(canonical_asset_id),
    effective_start TEXT NOT NULL,
    effective_end TEXT NOT NULL,
    predecessor_version_id TEXT REFERENCES provider_asset_mapping(mapping_version_id),
    created_at TEXT NOT NULL,
    CHECK (effective_start <= effective_end)
) STRICT;

CREATE INDEX IF NOT EXISTS provider_asset_mapping_lookup
    ON provider_asset_mapping(provider, provider_code, effective_start, effective_end);

CREATE TABLE IF NOT EXISTS provider_asset_mapping_current (
    provider TEXT NOT NULL,
    provider_code TEXT NOT NULL,
    current_mapping_version_id TEXT NOT NULL REFERENCES provider_asset_mapping(mapping_version_id),
    as_of TEXT NOT NULL,
    PRIMARY KEY (provider, provider_code)
) STRICT;

CREATE TABLE IF NOT EXISTS compliance_profile_version (
    compliance_profile_version_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    account TEXT NOT NULL,
    allowed_purpose TEXT NOT NULL,
    retention_allowed INTEGER NOT NULL CHECK (retention_allowed IN (0, 1)),
    export_allowed INTEGER NOT NULL CHECK (export_allowed IN (0, 1)),
    confirmed_at TEXT NOT NULL,
    predecessor_version_id TEXT REFERENCES compliance_profile_version(compliance_profile_version_id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS calendar_version (
    calendar_version_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    market TEXT NOT NULL,
    zone TEXT NOT NULL,
    effective_start TEXT NOT NULL,
    effective_end TEXT NOT NULL,
    predecessor_version_id TEXT REFERENCES calendar_version(calendar_version_id),
    created_at TEXT NOT NULL,
    CHECK (effective_start <= effective_end)
) STRICT;

CREATE TABLE IF NOT EXISTS calendar_day (
    calendar_version_id TEXT NOT NULL REFERENCES calendar_version(calendar_version_id),
    local_date TEXT NOT NULL,
    date_kind TEXT NOT NULL CHECK (date_kind IN ('TRADING', 'HOLIDAY', 'HALF_DAY')),
    PRIMARY KEY (calendar_version_id, local_date)
) STRICT;

CREATE TABLE IF NOT EXISTS valuation_calendar_version (
    valuation_calendar_version_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    zone TEXT NOT NULL,
    effective_start TEXT NOT NULL,
    effective_end TEXT NOT NULL,
    predecessor_version_id TEXT REFERENCES valuation_calendar_version(valuation_calendar_version_id),
    created_at TEXT NOT NULL,
    CHECK (effective_start <= effective_end)
) STRICT;

CREATE TABLE IF NOT EXISTS market_rule_profile_version (
    market_rule_profile_version_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    market TEXT NOT NULL,
    effective_start TEXT NOT NULL,
    effective_end TEXT NOT NULL,
    predecessor_version_id TEXT REFERENCES market_rule_profile_version(market_rule_profile_version_id),
    created_at TEXT NOT NULL,
    CHECK (effective_start <= effective_end)
) STRICT;

CREATE TABLE IF NOT EXISTS data_version (
    data_version_id TEXT PRIMARY KEY,
    dataset TEXT NOT NULL,
    logical_key TEXT NOT NULL,
    content_id TEXT NOT NULL,
    predecessor_version_id TEXT REFERENCES data_version(data_version_id),
    revision_position INTEGER NOT NULL CHECK (revision_position > 0),
    created_at TEXT NOT NULL,
    CHECK (length(content_id) > 0),
    UNIQUE (dataset, logical_key, revision_position)
) STRICT;

CREATE INDEX IF NOT EXISTS data_version_lookup
    ON data_version(dataset, logical_key, revision_position);

CREATE TABLE IF NOT EXISTS current_data_version (
    dataset TEXT NOT NULL,
    logical_key TEXT NOT NULL,
    current_data_version_id TEXT NOT NULL REFERENCES data_version(data_version_id),
    as_of TEXT NOT NULL,
    PRIMARY KEY (dataset, logical_key)
) STRICT;

CREATE TABLE IF NOT EXISTS quality_issue_version (
    quality_issue_version_id TEXT PRIMARY KEY,
    data_version_id TEXT NOT NULL REFERENCES data_version(data_version_id),
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'REJECTED')),
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS universe_membership_version (
    universe_membership_version_id TEXT PRIMARY KEY,
    universe_version_id TEXT NOT NULL,
    canonical_asset_id TEXT NOT NULL REFERENCES asset_identity(canonical_asset_id),
    effective_start TEXT NOT NULL,
    effective_end TEXT NOT NULL,
    evidence_json TEXT NOT NULL CHECK (length(evidence_json) >= 2),
    created_at TEXT NOT NULL,
    CHECK (effective_start <= effective_end),
    UNIQUE (universe_version_id, canonical_asset_id, effective_start)
) STRICT;

CREATE INDEX IF NOT EXISTS universe_membership_lookup
    ON universe_membership_version(universe_version_id, canonical_asset_id, effective_start, effective_end);

CREATE TABLE IF NOT EXISTS fx_rate_version (
    fx_rate_version_id TEXT PRIMARY KEY,
    source_currency TEXT NOT NULL,
    target_currency TEXT NOT NULL,
    rate_date TEXT NOT NULL,
    rate TEXT NOT NULL,
    provider TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    provenance_id TEXT NOT NULL,
    predecessor_version_id TEXT REFERENCES fx_rate_version(fx_rate_version_id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS snapshot_version (
    snapshot_version_id TEXT PRIMARY KEY,
    manifest_content_id TEXT NOT NULL UNIQUE,
    manifest_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS experiment_manifest_version (
    experiment_manifest_version_id TEXT PRIMARY KEY,
    manifest_content_id TEXT NOT NULL UNIQUE,
    manifest_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS research_run_version (
    research_run_version_id TEXT PRIMARY KEY,
    experiment_manifest_version_id TEXT NOT NULL REFERENCES experiment_manifest_version(experiment_manifest_version_id),
    state_content_id TEXT NOT NULL UNIQUE,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TRIGGER IF NOT EXISTS workspace_immutable_update
BEFORE UPDATE ON workspace
BEGIN
    SELECT RAISE(ABORT, 'workspace is immutable');
END;

CREATE TRIGGER IF NOT EXISTS workspace_immutable_delete
BEFORE DELETE ON workspace
BEGIN
    SELECT RAISE(ABORT, 'workspace is immutable');
END;

CREATE TRIGGER IF NOT EXISTS asset_identity_immutable_update
BEFORE UPDATE ON asset_identity
BEGIN
    SELECT RAISE(ABORT, 'asset identity is immutable');
END;

CREATE TRIGGER IF NOT EXISTS asset_identity_immutable_delete
BEFORE DELETE ON asset_identity
BEGIN
    SELECT RAISE(ABORT, 'asset identity is immutable');
END;

CREATE TRIGGER IF NOT EXISTS asset_master_version_immutable_update
BEFORE UPDATE ON asset_master_version
BEGIN
    SELECT RAISE(ABORT, 'asset master versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS asset_master_version_immutable_delete
BEFORE DELETE ON asset_master_version
BEGIN
    SELECT RAISE(ABORT, 'asset master versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS provider_asset_mapping_immutable_update
BEFORE UPDATE ON provider_asset_mapping
BEGIN
    SELECT RAISE(ABORT, 'provider asset mappings are immutable');
END;

CREATE TRIGGER IF NOT EXISTS provider_asset_mapping_immutable_delete
BEFORE DELETE ON provider_asset_mapping
BEGIN
    SELECT RAISE(ABORT, 'provider asset mappings are immutable');
END;

CREATE TRIGGER IF NOT EXISTS compliance_profile_version_immutable_update
BEFORE UPDATE ON compliance_profile_version
BEGIN
    SELECT RAISE(ABORT, 'compliance profile versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS compliance_profile_version_immutable_delete
BEFORE DELETE ON compliance_profile_version
BEGIN
    SELECT RAISE(ABORT, 'compliance profile versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS calendar_version_immutable_update
BEFORE UPDATE ON calendar_version
BEGIN
    SELECT RAISE(ABORT, 'calendar versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS calendar_version_immutable_delete
BEFORE DELETE ON calendar_version
BEGIN
    SELECT RAISE(ABORT, 'calendar versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS calendar_day_immutable_update
BEFORE UPDATE ON calendar_day
BEGIN
    SELECT RAISE(ABORT, 'calendar days are immutable');
END;

CREATE TRIGGER IF NOT EXISTS calendar_day_immutable_delete
BEFORE DELETE ON calendar_day
BEGIN
    SELECT RAISE(ABORT, 'calendar days are immutable');
END;

CREATE TRIGGER IF NOT EXISTS valuation_calendar_version_immutable_update
BEFORE UPDATE ON valuation_calendar_version
BEGIN
    SELECT RAISE(ABORT, 'valuation calendar versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS valuation_calendar_version_immutable_delete
BEFORE DELETE ON valuation_calendar_version
BEGIN
    SELECT RAISE(ABORT, 'valuation calendar versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS market_rule_profile_version_immutable_update
BEFORE UPDATE ON market_rule_profile_version
BEGIN
    SELECT RAISE(ABORT, 'market rule profile versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS market_rule_profile_version_immutable_delete
BEFORE DELETE ON market_rule_profile_version
BEGIN
    SELECT RAISE(ABORT, 'market rule profile versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS data_version_immutable_update
BEFORE UPDATE ON data_version
BEGIN
    SELECT RAISE(ABORT, 'data versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS data_version_immutable_delete
BEFORE DELETE ON data_version
BEGIN
    SELECT RAISE(ABORT, 'data versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS quality_issue_version_immutable_update
BEFORE UPDATE ON quality_issue_version
BEGIN
    SELECT RAISE(ABORT, 'quality issue versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS quality_issue_version_immutable_delete
BEFORE DELETE ON quality_issue_version
BEGIN
    SELECT RAISE(ABORT, 'quality issue versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS universe_membership_version_immutable_update
BEFORE UPDATE ON universe_membership_version
BEGIN
    SELECT RAISE(ABORT, 'universe membership versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS universe_membership_version_immutable_delete
BEFORE DELETE ON universe_membership_version
BEGIN
    SELECT RAISE(ABORT, 'universe membership versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS fx_rate_version_immutable_update
BEFORE UPDATE ON fx_rate_version
BEGIN
    SELECT RAISE(ABORT, 'fx rate versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS fx_rate_version_immutable_delete
BEFORE DELETE ON fx_rate_version
BEGIN
    SELECT RAISE(ABORT, 'fx rate versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS snapshot_version_immutable_update
BEFORE UPDATE ON snapshot_version
BEGIN
    SELECT RAISE(ABORT, 'snapshot versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS snapshot_version_immutable_delete
BEFORE DELETE ON snapshot_version
BEGIN
    SELECT RAISE(ABORT, 'snapshot versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS experiment_manifest_version_immutable_update
BEFORE UPDATE ON experiment_manifest_version
BEGIN
    SELECT RAISE(ABORT, 'experiment manifest versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS experiment_manifest_version_immutable_delete
BEFORE DELETE ON experiment_manifest_version
BEGIN
    SELECT RAISE(ABORT, 'experiment manifest versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS research_run_version_immutable_update
BEFORE UPDATE ON research_run_version
BEGIN
    SELECT RAISE(ABORT, 'research run versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS research_run_version_immutable_delete
BEFORE DELETE ON research_run_version
BEGIN
    SELECT RAISE(ABORT, 'research run versions are immutable');
END;
