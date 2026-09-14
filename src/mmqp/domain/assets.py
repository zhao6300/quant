from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import UUID

from mmqp.domain.errors import DomainError, ProblemV1

MarketName = Literal["A_SHARE", "HONG_KONG", "UNITED_STATES"]
AssetType = Literal["EQUITY", "ETF", "OPEN_END_FUND"]
AssetLifecycleStatus = Literal["UNLISTED", "ACTIVE", "SUSPENDED", "DELISTED", "EXPIRED", "UNKNOWN"]

SUPPORTED_MARKETS = frozenset({"A_SHARE", "HONG_KONG", "UNITED_STATES"})
SUPPORTED_ASSET_TYPES = frozenset({"EQUITY", "ETF", "OPEN_END_FUND"})
SUPPORTED_LIFECYCLE_STATUSES = frozenset(
    {"UNLISTED", "ACTIVE", "SUSPENDED", "DELISTED", "EXPIRED", "UNKNOWN"}
)


@dataclass(frozen=True, slots=True)
class AssetIdentity:
    market: str
    asset_type: str
    exchange: str
    local_code: str

    @property
    def canonical_id(self) -> str:
        from hashlib import sha256

        normalized = "|".join(
            component.strip().casefold()
            for component in (self.market, self.asset_type, self.exchange, self.local_code)
        )
        return sha256(normalized.encode("utf-8")).hexdigest()[:20].upper()


@dataclass(frozen=True, slots=True)
class AssetVersion:
    version_id: str
    asset_id: str
    identity: AssetIdentity
    name: str
    trading_currency: str
    lifecycle_status: str
    effective_from: date
    effective_to: date | None
    predecessor_id: str | None


ProviderAssetMappingId = UUID


@dataclass(frozen=True, slots=True)
class ProviderAssetMapping:
    provider: str
    provider_code: str
    asset_id: str
    effective_from: date
    effective_to: date | None
    mapping_id: ProviderAssetMappingId | None = None

    @property
    def id(self) -> ProviderAssetMappingId | None:
        return self.mapping_id


@dataclass(frozen=True, slots=True)
class ProviderAssetMappingResolution:
    status: str
    provider: str
    provider_code: str
    observation_date: date
    asset_id: str | None = None
    matches: tuple[ProviderAssetMapping, ...] = ()


class AssetRecordValidationError(DomainError):
    def __init__(self, fields: list[str] | None = None):
        super().__init__(
            ProblemV1(
                kind="asset/record-invalid",
                title="Invalid asset record",
                status=400,
                detail=None if fields is None else f"asset record invalid: {', '.join(fields)}",
            )
        )
        self.fields = fields


class AssetOverlappingVersionError(DomainError):
    def __init__(self, fields: list[str] | None = None):
        super().__init__(
            ProblemV1(
                kind="asset/overlap",
                title="Overlapping asset versions",
                status=409,
                detail=None if fields is None else f"asset versions overlap: {', '.join(fields)}",
            )
        )
        self.fields = fields


class MappingOperationError(DomainError):
    def __init__(self, *, status: int, title: str, detail: str):
        kind = "asset/mapping-conflict" if status == 409 else "asset/mapping-invalid"
        super().__init__(ProblemV1(kind=kind, title=title, status=status, detail=detail))
