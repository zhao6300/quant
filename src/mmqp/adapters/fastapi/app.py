from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Generator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mmqp import PLATFORM_VERSION
from mmqp.adapters.data_connectors.registry import daily_bar_connectors
from mmqp.adapters.source_ingestion import (
    SourceDailyBarCommand,
    SourceDailyBarHistoryCommand,
    SourceDailyBarIngestionService,
)
from mmqp.adapters.sqlite.asset_repository import SqliteAssetRegistryRepository
from mmqp.adapters.sqlite.baselines import seed_market_baseline
from mmqp.adapters.sqlite.calendars import (
    SqliteTradingCalendarRepository,
    SqliteValuationCalendarRepository,
)
from mmqp.adapters.sqlite.data_versions import SqliteDataVersionRepository
from mmqp.adapters.sqlite.market_rules import SqliteMarketRuleRepository
from mmqp.adapters.sqlite.query_source import SqliteQuerySource
from mmqp.adapters.sqlite.workspace_repository import SqliteWorkspaceRepository
from mmqp.application.assets import AssetRegistryService, RegisterAssetRequest
from mmqp.application.calendars import CalendarService
from mmqp.application.ingestion import DataIngestionService
from mmqp.application.market_rules import MarketRuleService
from mmqp.application.queries import (
    LIVE_SNAPSHOT_ID,
    SUPPORTED_QUERY_FILTERS,
    QueryFilter,
    ReadonlyQueryService,
    TypedQuery,
)
from mmqp.application.run_submission import (
    ResearchRunRequest,
    RunSubmissionService,
)
from mmqp.application.sources import list_data_sources, source_usage_payload
from mmqp.application.stocks import stock_catalog
from mmqp.application.workspaces import WorkspaceService
from mmqp.domain.assets import AssetVersion, ProviderAssetMapping
from mmqp.domain.calendars import (
    AlignedObservation,
    AlignmentCandidate,
    TradingCalendarDay,
    TradingCalendarVersion,
    TradingSession,
    ValuationCalendarVersion,
)
from mmqp.domain.errors import DomainError, ProblemV1
from mmqp.domain.ingestion import DailyBar
from mmqp.domain.market_rules import (
    EvaluatedTrade,
    HaltStatus,
    MarketRuleProfile,
    MarketRuleResolutionError,
    SessionKind,
    SubmittedTrade,
    TradeSide,
)
from mmqp.domain.workspace import WorkspaceRecord
from mmqp.interfaces.schemas import QueryRequestModel
from mmqp.kernels.market_rules import PureMarketRuleEvaluator
from mmqp.ports.assets import AssetRegistryRepository
from mmqp.ports.calendars import TradingCalendarRepository, ValuationCalendarRepository
from mmqp.ports.market_rules import MarketRuleRepository
from mmqp.ports.workspace_repository import WorkspaceRepository

frontend_dist = Path(__file__).resolve().parents[4] / "frontend" / "dist"
control_database_path = Path("/tmp/mmqp-platform-control.sqlite3")

@asynccontextmanager
async def platform_lifespan(_: FastAPI) -> AsyncIterator[None]:
    seed_market_baseline(control_database_path)
    yield


app = FastAPI(
    title="Multi-Market Quant Platform",
    version=PLATFORM_VERSION,
    lifespan=platform_lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.mount("/assets", StaticFiles(directory=frontend_dist / "assets", check_dir=False), name="assets")


@app.get("/", include_in_schema=False)
def read_frontend() -> Response:
    index_html = frontend_dist / "index.html"
    if index_html.is_file():
        return FileResponse(index_html, headers={"Cache-Control": "no-store"})
    return HTMLResponse(
        """<!doctype html><html lang="en"><head><meta charset="utf-8">"""
        """<title>MMQP</title></head><body>"""
        """<h1>MMQP</h1><p>Run ./scripts/install.sh to build the web console.</p>"""
        """</body></html>"""
    )


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.problem.status, content=exc.problem.to_dict())


class CreateWorkspaceRequest(BaseModel):
    path: str
    display_name: str | None = Field(default=None, min_length=1, max_length=120)


def get_workspace_repository() -> WorkspaceRepository:
    return SqliteWorkspaceRepository("/tmp/mmqp-workspaces.sqlite3")


def workspace_service(
    repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> WorkspaceService:
    return WorkspaceService(repository)


def get_asset_registry_service(
    repository: Annotated[SqliteAssetRegistryRepository, Depends(get_asset_registry_store)],
) -> AssetRegistryService:
    return AssetRegistryService(repository)


def get_asset_registry(factory: Callable[[], AssetRegistryRepository]) -> AssetRegistryService:
    return AssetRegistryService(factory())


def get_asset_registry_store() -> Generator[SqliteAssetRegistryRepository]:
    yield SqliteAssetRegistryRepository("/tmp/mmqp-data/read.sqlite")


class TradingSessionModel(BaseModel):
    start: str
    end: str
    kind: SessionKind = "regular"


class TradingCalendarDayModel(BaseModel):
    market: str
    exchange: str
    date: date
    kind: Literal["closed", "full", "half"]
    sessions: tuple[TradingSessionModel, ...] = ()


class TradingCalendarRequest(BaseModel):
    version_id: str = Field(min_length=1, max_length=120)
    market: str = Field(min_length=1, max_length=40)
    exchange: str = Field(min_length=1, max_length=64)
    timezone: str = Field(min_length=1, max_length=64)
    effective_from: date
    effective_to: date | None = None
    days: tuple[TradingCalendarDayModel, ...] = ()


class ValuationCalendarRequest(BaseModel):
    version_id: str = Field(min_length=1, max_length=120)
    market: str = Field(min_length=1, max_length=40)
    timezone: str = Field(min_length=1, max_length=64)
    effective_from: date
    effective_to: date | None = None


class MarketRuleProfileRequest(BaseModel):
    version_id: str = Field(min_length=1, max_length=120)
    market: str = Field(min_length=1, max_length=40)
    exchange: str = Field(min_length=1, max_length=64)
    asset_type: str = Field(min_length=1, max_length=40)
    effective_from: date
    effective_to: date | None = None
    trading_lot: int
    tick_size: Decimal
    price_limit_rule: Literal["NONE", "STATIC_PERCENTAGE_BASE_REFERENCE", "PROVIDER_BAND_REQUIRED"]
    price_limit_percent: Decimal | None = None
    sell_availability_rule: Literal["SAME_MARKET_DATE", "NEXT_OPEN_MARKET_DATE"]
    security_settlement_open_dates: int
    cash_settlement_open_dates: int
    permitted_session_types: tuple[SessionKind, ...]


class AlignmentRequest(BaseModel):
    alignment_date: date
    decision_timestamp: datetime
    calendar_id: str
    candidates: tuple[AlignmentCandidateModel, ...]


class AlignmentCandidateModel(BaseModel):
    source_market_date: date
    provider_available_at: datetime


class TradeSubmissionRequest(BaseModel):
    market: str = Field(min_length=1, max_length=40)
    exchange: str = Field(min_length=1, max_length=64)
    asset_type: str = Field(min_length=1, max_length=40)
    trade_date: date
    side: TradeSide
    requested_quantity: Decimal
    requested_price: Decimal = Field(gt=0)
    session_kind: SessionKind = "regular"
    market_data_price_limit_percent: Decimal | None = None
    market_data_price_band_percent: Decimal | None = None
    halt_status: HaltStatus = "ACTIVE"
    reference_price: Decimal | None = None
    sellable_quantity: Decimal = Field(ge=0)


class QueryFilterModel(BaseModel):
    field: str
    values: tuple[str, ...] = ()


class AssetRequestModel(BaseModel):
    market: str = Field(min_length=1, max_length=40)
    asset_type: str = Field(min_length=1, max_length=40)
    exchange: str = Field(min_length=1, max_length=64)
    local_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=256)
    trading_currency: str = Field(min_length=3, max_length=3)
    lifecycle_status: str = Field(min_length=1, max_length=40)
    effective_from: date
    effective_to: date | None = None


class ProviderAssetMappingRequestModel(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    provider_code: str = Field(min_length=1, max_length=128)
    asset_id: str = Field(min_length=1, max_length=128)
    effective_from: date
    effective_to: date | None = None


class ResearchRunRequestModel(BaseModel):
    snapshot_id: str = LIVE_SNAPSHOT_ID
    start_date: date
    end_date: date
    base_currency: str
    factor_definition_version: str = Field(min_length=1, max_length=120)
    universe_version: str = Field(min_length=1, max_length=120)
    portfolio_definition_version: str = Field(min_length=1, max_length=120)
    strategy_version: str = Field(min_length=1, max_length=120)
    transaction_cost_model_version: str = Field(min_length=1, max_length=120)
    risk_model_version: str = Field(min_length=1, max_length=120)


class SourceDailyBarRequestModel(BaseModel):
    market: str = Field(min_length=1, max_length=40)
    exchange: str = Field(min_length=1, max_length=64)
    canonical_asset_id: str = Field(min_length=1, max_length=128)
    provider_code: str = Field(min_length=1, max_length=128)
    trading_date: date


def get_trading_calendar_repository() -> Generator[TradingCalendarRepository]:
    database = control_database_path
    trading_repository = SqliteTradingCalendarRepository(database)
    try:
        yield trading_repository
    finally:
        trading_repository.close()


def get_valuation_calendar_repository() -> Generator[ValuationCalendarRepository]:
    database = control_database_path
    valuation_repository = SqliteValuationCalendarRepository(database)
    try:
        yield valuation_repository
    finally:
        valuation_repository.close()


def get_market_rule_repository() -> Generator[MarketRuleRepository]:
    database = control_database_path
    repository = SqliteMarketRuleRepository(database)
    try:
        yield repository
    finally:
        repository.close()


def get_calendar_service(
    trading_repository: Annotated[TradingCalendarRepository, Depends(get_trading_calendar_repository)],
    valuation_repository: Annotated[ValuationCalendarRepository, Depends(get_valuation_calendar_repository)],
) -> CalendarService:
    return CalendarService(trading_repository, valuation_repository)


def get_market_rule_service(
    repository: Annotated[MarketRuleRepository, Depends(get_market_rule_repository)],
) -> MarketRuleService:
    return MarketRuleService(repository)


def get_query_source() -> SqliteQuerySource:
    root = Path("/tmp/mmqp-data")
    return SqliteQuerySource(str(root / "read.sqlite"))


def get_query_service(
    source: Annotated[SqliteQuerySource, Depends(get_query_source)],
) -> ReadonlyQueryService:
    return ReadonlyQueryService(source, SUPPORTED_QUERY_FILTERS)


def get_source_ingestion_service() -> SourceDailyBarIngestionService:
    database = str(Path("/tmp/mmqp-source-ingestion.sqlite3"))
    ingestion = DataIngestionService(
        SqliteDataVersionRepository(database),
        SqliteTradingCalendarRepository(database),
        SqliteValuationCalendarRepository(database),
    )
    return SourceDailyBarIngestionService(daily_bar_connectors(), ingestion)


WorkspaceRepo = Annotated[WorkspaceRepository, Depends(get_workspace_repository)]
GeneratedCalendarService = Annotated[
    CalendarService,
    Depends(get_calendar_service),
]
MarketRuleServiceDep = Annotated[MarketRuleService, Depends(get_market_rule_service)]


def _to_trading_calendar(request: TradingCalendarRequest) -> TradingCalendarVersion:
    return TradingCalendarVersion(
        version_id=request.version_id,
        market=request.market,
        exchange=request.exchange,
        timezone=request.timezone,
        effective_from=request.effective_from,
        effective_to=request.effective_to,
        days=tuple(
            TradingCalendarDay(
                market=day.market,
                exchange=day.exchange,
                date=day.date,
                kind=day.kind,
                sessions=tuple(
                    TradingSession(start=session.start, end=session.end, kind=session.kind)
                    for session in day.sessions
                ),
            )
            for day in request.days
        ),
    )


def _to_market_rule_profile(request: MarketRuleProfileRequest) -> MarketRuleProfile:
    return MarketRuleProfile(
        version_id=request.version_id,
        market=request.market,
        exchange=request.exchange,
        asset_type=request.asset_type,
        effective_from=request.effective_from,
        effective_to=request.effective_to,
        trading_lot=request.trading_lot,
        tick_size=request.tick_size,
        price_limit_rule=request.price_limit_rule,
        price_limit_percent=request.price_limit_percent,
        sell_availability_rule=request.sell_availability_rule,
        security_settlement_open_dates=request.security_settlement_open_dates,
        cash_settlement_open_dates=request.cash_settlement_open_dates,
        permitted_session_types=request.permitted_session_types,
    )


def _to_trade(request: TradeSubmissionRequest) -> SubmittedTrade:
    return SubmittedTrade(
        market=request.market,
        exchange=request.exchange,
        asset_type=request.asset_type,
        trade_date=request.trade_date,
        side=request.side,
        requested_quantity=request.requested_quantity,
        requested_price=request.requested_price,
        session_kind=request.session_kind,
        market_data_price_limit_percent=request.market_data_price_limit_percent,
        market_data_price_band_percent=request.market_data_price_band_percent,
        halt_status=request.halt_status,
        reference_price=request.reference_price,
        sellable_quantity=request.sellable_quantity,
    )


def _registration_error(exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.problem.status, content=exc.problem.to_dict())


def _domain_error(status: int, detail: str) -> DomainError:
    retry = "never" if status in {400, 404} else "retry-with-backoff"
    return DomainError(
        ProblemV1(
            kind="platform/request-error",
            title=detail,
            status=status,
            detail=detail,
            retry=retry,
        )
    )


def _aware_clock(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise _domain_error(400, "decision_timestamp must be timezone-aware")
    return value


@app.get("/api/v1/status")
def read_status(
    repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> dict[str, Any]:
    return {
        "platform_version": PLATFORM_VERSION,
        "workspace_count": len(repository.list()),
        "schema_version": 1,
        "compatible_restore_schema_versions": [1],
    }


@app.get("/api/v1/data-sources")
def list_sources() -> list[dict[str, Any]]:
    return [
        {
            "id": source.id,
            "provider": source.provider,
            "source_id": source.source_id,
            "display_name": source.display_name,
            "category": source.category,
            "scope": source.scope,
            "frequency": source.frequency,
            "implementation_status": source.implementation_status,
            "requires_auth": source.requires_auth,
            "documentation_url": source.documentation_url,
            "note": source.note,
            "usage": source_usage_payload(source),
        }
        for source in list_data_sources()
    ]


@app.get("/api/v1/stocks")
def get_stock_choices(
    market: str,
    query: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    choices = stock_catalog(market=market, query=query, limit=limit)
    return {
        "market": market.upper(),
        "query": query,
        "stocks": [
            {
                "symbol": choice.symbol,
                "name": choice.name,
                "market": choice.market,
                "exchange": choice.exchange,
                "currency": choice.currency,
            }
            for choice in choices
        ],
    }


@app.post("/api/v1/workspaces", status_code=201)
def create_workspace(
    request: CreateWorkspaceRequest,
    service: Annotated[WorkspaceService, Depends(workspace_service)],
) -> WorkspaceRecord:
    return service.create(request.path, request.display_name)


@app.post("/api/v1/workspaces/open")
def open_workspace(
    request: CreateWorkspaceRequest,
    service: Annotated[WorkspaceService, Depends(workspace_service)],
) -> WorkspaceRecord:
    return service.open(request.path)


@app.get("/api/v1/workspaces")
def list_workspaces(
    repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> list[WorkspaceRecord]:
    return repository.list()


@app.post("/api/v1/assets", status_code=201)
def register_asset(
    request: AssetRequestModel,
    service: Annotated[AssetRegistryService, Depends(get_asset_registry_service)],
) -> AssetVersion:
    return service.register(
        RegisterAssetRequest(
            market=request.market,
            asset_type=request.asset_type,
            exchange=request.exchange,
            local_code=request.local_code,
            name=request.name,
            trading_currency=request.trading_currency,
            lifecycle_status=request.lifecycle_status,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
        )
    )


@app.get("/api/v1/assets/{asset_id}")
def resolve_asset(
    asset_id: str,
    service: Annotated[AssetRegistryService, Depends(get_asset_registry_service)],
    effective_at: date | None = None,
) -> AssetVersion:
    asset = service.as_of(asset_id, effective_at) if effective_at else service.get(asset_id)
    if asset is None:
        raise _domain_error(404, "asset not found")
    return asset


@app.post("/api/v1/assets/provider-mappings", status_code=201)
def create_provider_asset_mapping(
    request: ProviderAssetMappingRequestModel,
    service: Annotated[AssetRegistryService, Depends(get_asset_registry_service)],
) -> ProviderAssetMapping:
    return service.build_provider_mapping(
        provider=request.provider,
        provider_code=request.provider_code,
        asset_id=request.asset_id,
        effective_from=request.effective_from,
        effective_to=request.effective_to,
    )


@app.get("/api/v1/calendars/trading")
def resolve_trading_calendar(
    market: str,
    exchange: str,
    as_of: date,
    service: GeneratedCalendarService,
) -> TradingCalendarVersion:
    return service.select_trading(market, exchange, as_of)


@app.post("/api/v1/calendars/trading", status_code=201)
def create_trading_calendar(
    request: TradingCalendarRequest,
    service: GeneratedCalendarService,
) -> TradingCalendarVersion:
    return service.register_trading(_to_trading_calendar(request))


@app.get("/api/v1/calendars/valuation")
def resolve_valuation_calendar(
    market: str,
    as_of: date,
    service: GeneratedCalendarService,
) -> ValuationCalendarVersion:
    return service.select_valuation(market, as_of)


@app.post("/api/v1/calendars/valuation", status_code=201)
def create_valuation_calendar(
    request: ValuationCalendarRequest,
    service: GeneratedCalendarService,
) -> ValuationCalendarVersion:
    return service.register_valuation(
        ValuationCalendarVersion(
            version_id=request.version_id,
            market=request.market,
            timezone=request.timezone,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
        )
    )


@app.get("/api/v1/market-rules")
def resolve_market_rule(
    market: str,
    exchange: str,
    asset_type: str,
    as_of: date,
    service: MarketRuleServiceDep,
) -> MarketRuleProfile:
    selection = service.resolve(market, exchange, asset_type, as_of)
    if selection.profile is None:
        status = 404 if not selection.matching_profile_ids else 409
        raise MarketRuleResolutionError(
            status=status,
            resolution_status="missing" if not selection.matching_profile_ids else "ambiguous",
            detail=f"{selection.matching_profile_ids}",
        )
    return selection.profile


@app.get("/api/v1/market-rules/list")
def list_market_rules(
    service: MarketRuleServiceDep,
    market: str | None = None,
    exchange: str | None = None,
    asset_type: str | None = None,
) -> list[MarketRuleProfile]:
    return service.list(market, exchange, asset_type)


@app.post("/api/v1/market-rules", status_code=201)
def create_market_rule(
    request: MarketRuleProfileRequest,
    service: MarketRuleServiceDep,
) -> MarketRuleProfile:
    return service.register(_to_market_rule_profile(request))


@app.post("/api/v1/calendars/alignment")
def align_market_observations(
    request: AlignmentRequest,
    service: GeneratedCalendarService,
    trading_repository: Annotated[TradingCalendarRepository, Depends(get_trading_calendar_repository)],
) -> list[AlignedObservation]:
    matching = trading_repository.list()
    matching_calendar = next((item for item in matching if item.version_id == request.calendar_id), None)
    if matching_calendar is None:
        raise _domain_error(404, "calendar not found")
    decision = _aware_clock(request.decision_timestamp)
    return list(
        service.align_observations(
            alignment_date=request.alignment_date,
            decision_timestamp=decision,
            candidates=tuple(
                AlignmentCandidate(
                    source_market_date=candidate.source_market_date,
                    provider_available_at=candidate.provider_available_at,
                )
                for candidate in request.candidates
            ),
            aligned_calendar=matching_calendar,
        )
    )


@app.post("/api/v1/market-rules/evaluate")
def evaluate_market_rule(
    request: TradeSubmissionRequest,
    service: MarketRuleServiceDep,
    calendar_service: GeneratedCalendarService,
) -> EvaluatedTrade:
    submitted = _to_trade(request)
    market_selection = service.resolve(
        submitted.market, submitted.exchange, submitted.asset_type, submitted.trade_date
    )
    matches = market_selection.matching_profile_ids
    selected = market_selection.profile
    if selected is None:
        if len(matches) > 1:
            raise _domain_error(409, "ambiguous market-rule profile")
        raise _domain_error(404, "market-rule profile not found")
    calendar = calendar_service.select_trading(submitted.market, submitted.exchange, submitted.trade_date)
    next_permitted_date = PureMarketRuleEvaluator.next_permitted_date(
        profile=selected, calendar=calendar, trade_date=submitted.trade_date
    )
    return PureMarketRuleEvaluator().evaluate_trade(
        submitted=submitted,
        profile=selected,
        calendar=calendar,
        matches=matches,
        next_permitted_date=next_permitted_date,
    )


@app.post(
    "/api/v1/queries/results",
)
def query_dataset(
    request: QueryRequestModel,
    service: Annotated[ReadonlyQueryService, Depends(get_query_service)],
) -> dict[str, Any]:
    result = service.query(
        TypedQuery(
            snapshot_id=request.snapshot_id,
            dataset=request.dataset,
            filters=tuple(
                QueryFilter(field=item.field, values=tuple(item.values)) for item in request.filters
            ),
        ),
    )
    return {
        "snapshot_id": result.snapshot_id,
        "query": result.query,
        "matching_count": result.matching_count,
        "returned_count": result.returned_count,
        "applied_filter_count": result.applied_filter_count,
        "additional_results": result.additional_results,
        "rows": result.rows,
    }


@app.post("/api/v1/runs", status_code=202)
def submit_run(request: ResearchRunRequestModel) -> dict[str, Any]:
    submission = RunSubmissionService([LIVE_SNAPSHOT_ID])
    receipt = submission.submit(
        ResearchRunRequest(
            snapshot_id=request.snapshot_id,
            start_date=request.start_date,
            end_date=request.end_date,
            base_currency=request.base_currency,
            factor_definition_version=request.factor_definition_version,
            universe_version=request.universe_version,
            portfolio_definition_version=request.portfolio_definition_version,
            strategy_version=request.strategy_version,
            transaction_cost_model_version=request.transaction_cost_model_version,
            risk_model_version=request.risk_model_version,
        )
    )
    return {
        "snapshot_id": receipt.snapshot_id,
        "request": receipt.request,
        "result_kind": receipt.result_kind,
        "disclaimer": receipt.disclaimer,
        "run_created": receipt.run_created,
    }


@app.post("/api/v1/data-sources/{source_id}/daily-bars", status_code=201)
def ingest_source_daily_bar(
    source_id: str,
    request: SourceDailyBarRequestModel,
    service: Annotated[SourceDailyBarIngestionService, Depends(get_source_ingestion_service)],
) -> dict[str, Any]:
    ingest = service.ingest(
        SourceDailyBarCommand(
            source_id=source_id,
            market=request.market,
            exchange=request.exchange,
            canonical_asset_id=request.canonical_asset_id,
            provider_code=request.provider_code,
            trading_date=request.trading_date,
        )
    )
    observation = ingest.version.observation
    if not isinstance(observation, DailyBar):
        raise _domain_error(500, "source ingest returned a non-daily-bar observation")
    return {
        "dataset": ingest.dataset,
        "version_id": ingest.version.version_id,
        "revision_id": ingest.version.revision_id,
        "asset_id": ingest.version.canonical_asset_id,
        "provider_code": observation.provider_code,
        "provider_available_at": observation.provider_available_at.isoformat(),
        "retrieved_at": observation.retrieved_at.isoformat(),
        "provider": observation.provider,
        "provenance_id": observation.provenance_id,
    }


@app.get("/api/v1/data-sources/{source_id}/quote")
def get_source_quote(
    source_id: str,
    market: str,
    exchange: str,
    symbol: str,
    trading_date: date,
    service: Annotated[
        SourceDailyBarIngestionService, Depends(get_source_ingestion_service)
    ],
) -> dict[str, Any]:
    preview = service.preview(
        SourceDailyBarCommand(
            source_id=source_id,
            market=market,
            exchange=exchange,
            canonical_asset_id=f"ASSET-{source_id}:{symbol}",
            provider_code=symbol,
            trading_date=trading_date,
        )
    )
    observation = preview.observation
    if not isinstance(observation, DailyBar):
        raise _domain_error(500, "quote preview returned a non-daily-bar observation")
    return {
        "source_id": preview.source_id,
        "market": market.upper(),
        "exchange": exchange.upper(),
        "canonical_asset_id": preview.canonical_asset_id,
        "provider_code": observation.provider_code,
        "trading_date": observation.trading_date.isoformat(),
        "open": str(observation.open),
        "high": str(observation.high),
        "low": str(observation.low),
        "close": str(observation.close),
        "volume": str(observation.volume),
        "turnover": str(observation.turnover),
        "trading_currency": observation.trading_currency,
        "provider_available_at": observation.provider_available_at.isoformat(),
        "retrieved_at": observation.retrieved_at.isoformat(),
        "provider": observation.provider,
        "provenance_id": observation.provenance_id,
    }


@app.get("/api/v1/data-sources/{source_id}/history")
def get_source_history(
    source_id: str,
    market: str,
    exchange: str,
    symbol: str,
    trading_date: date,
    service: Annotated[
        SourceDailyBarIngestionService, Depends(get_source_ingestion_service)
    ],
    limit: int = 20,
) -> dict[str, Any]:
    preview = service.history(
        SourceDailyBarHistoryCommand(
            source_id=source_id,
            market=market,
            exchange=exchange,
            canonical_asset_id=f"ASSET-{source_id}:{symbol}",
            provider_code=symbol,
            end_date=trading_date,
            start_date=trading_date - timedelta(days=max(limit - 1, 0)),
            limit=limit,
        )
    )
    return {
        "source_id": preview.source_id,
        "market": preview.market.upper(),
        "exchange": preview.exchange.upper(),
        "provider_code": preview.provider_code,
        "canonical_asset_id": preview.canonical_asset_id,
        "bars": [
            {
                "trading_date": observation.trading_date.isoformat(),
                "open": str(observation.open),
                "high": str(observation.high),
                "low": str(observation.low),
                "close": str(observation.close),
                "volume": str(observation.volume),
                "turnover": str(observation.turnover),
                "trading_currency": observation.trading_currency,
                "provider": observation.provider,
                "provider_code": observation.provider_code,
                "provenance_id": observation.provenance_id,
            }
            for observation in preview.observations
        ],
    }


@app.get("/api/v1/queries/{dataset}")
def get_query_dataset(
    dataset: str,
    service: Annotated[ReadonlyQueryService, Depends(get_query_service)],
    snapshot_id: str = LIVE_SNAPSHOT_ID,
    field: list[str] | None = None,
    value: list[str] | None = None,
) -> dict[str, Any]:
    if dataset not in SUPPORTED_QUERY_FILTERS:
        raise _domain_error(400, f"unsupported dataset {dataset}")
    if len(field or []) != len(value or []):
        raise _domain_error(422, "filter field/value counts differ")
    filters = tuple(
        QueryFilter(field=current_field, values=(current_value,))
        for current_field, current_value in zip(field or [], value or [], strict=True)
    )
    result = service.query(TypedQuery(snapshot_id=snapshot_id, dataset=dataset, filters=filters))
    return {
        "snapshot_id": result.snapshot_id,
        "query": result.query,
        "matching_count": result.matching_count,
        "returned_count": result.returned_count,
        "applied_filter_count": result.applied_filter_count,
        "additional_results": result.additional_results,
        "rows": result.rows,
    }
