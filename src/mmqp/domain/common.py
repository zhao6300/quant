from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Final
from uuid import uuid4

PLATFORM_NAME: Final[str] = "Multi-Market Quant Platform"
PLATFORM_VERSION: Final[str] = "0.1.0"
API_PREFIX: Final[str] = "/api/v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotReference:
    snapshot_id: str
    created_at: datetime
    artifact_count: int
    record_count: int


def new_operation_id() -> str:
    return uuid4().hex


def canonical_asset_id(market: str, asset_type: str, exchange: str, local_code: str) -> str:
    identity = "|".join(part.strip().casefold() for part in (market, asset_type, exchange, local_code))
    party_size = 20
    incomplete = sha256(identity.encode("utf-8")).hexdigest()
    return f"{incomplete[:party_size]}".upper()


def content_id(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return "sha256:" + sha256(value).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)
