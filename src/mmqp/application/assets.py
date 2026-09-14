from dataclasses import dataclass
from datetime import date
from typing import Literal
from uuid import uuid4

from mmqp.domain.assets import (
    SUPPORTED_ASSET_TYPES,
    SUPPORTED_LIFECYCLE_STATUSES,
    SUPPORTED_MARKETS,
    AssetIdentity,
    AssetRecordValidationError,
    AssetVersion,
    ProviderAssetMapping,
    ProviderAssetMappingResolution,
)
from mmqp.ports.assets import AssetRegistryRepository

AssetTypeLiteral = Literal["EQUITY", "ETF", "OPEN_END_FUND"]
MarketLiteral = Literal["A_SHARE", "HONG_KONG", "UNITED_STATES"]
AssetLifecycleStatusLiteral = Literal["UNLISTED", "ACTIVE", "SUSPENDED", "DELISTED", "EXPIRED", "UNKNOWN"]


@dataclass(frozen=True, slots=True)
class RegisterAssetRequest:
    market: str
    asset_type: str
    exchange: str
    local_code: str
    name: str
    trading_currency: str
    lifecycle_status: str
    effective_from: date
    effective_to: date | None


@dataclass(frozen=True, slots=True)
class AssetValidationError:
    errors: tuple[str, ...] = ()


class AssetRegistryService:
    def __init__(self, repository: AssetRegistryRepository):
        self._repository = repository

    def register(self, request: RegisterAssetRequest) -> AssetVersion:
        self._validate(request)
        identity = AssetIdentity(
            market=request.market,
            asset_type=request.asset_type,
            exchange=request.exchange,
            local_code=request.local_code,
        )
        asset_id = identity.canonical_id
        existing = self._repository.find(asset_id)
        if existing is None:
            return self._create(
                request=request,
                identity=identity,
                asset_id=asset_id,
                effective_from=request.effective_from,
                predecessor_id=None,
            )
        if (
            existing.name == request.name
            and existing.trading_currency == request.trading_currency
            and existing.lifecycle_status == request.lifecycle_status
        ):
            return existing
        if (
            existing.name != request.name
            or existing.trading_currency != request.trading_currency
            or existing.lifecycle_status != request.lifecycle_status
        ):
            self._close(existing, request.effective_from)
        return self._create(
            request=request,
            identity=identity,
            asset_id=asset_id,
            effective_from=request.effective_from,
            predecessor_id=existing.version_id,
        )

    def get(self, asset_id: str) -> AssetVersion | None:
        return self._repository.find(asset_id)

    def history(self, asset_id: str) -> list[AssetVersion]:
        return self._repository.history(asset_id)

    def as_of(self, asset_id: str, observation_date: date) -> AssetVersion | None:
        return self._repository.as_of(asset_id, observation_date)

    def build_provider_mapping(
        self,
        *,
        provider: str,
        provider_code: str,
        asset_id: str,
        effective_from: date,
        effective_to: date | None,
    ) -> ProviderAssetMapping:
        mapping = ProviderAssetMapping(
            provider=provider,
            provider_code=provider_code,
            asset_id=asset_id,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        self._validate_provider_mapping(mapping)
        return self._repository.create_provider_mapping(mapping)

    def resolve_provider_mapping(
        self,
        *,
        provider: str,
        provider_code: str,
        observation_date: date,
    ) -> ProviderAssetMappingResolution:
        matches = self._repository.provider_mappings(
            provider=provider,
            provider_code=provider_code,
            observation_date=observation_date,
        )
        if len(matches) == 1:
            return ProviderAssetMappingResolution(
                status="resolved",
                provider=provider,
                provider_code=provider_code,
                observation_date=observation_date,
                asset_id=matches[0].asset_id,
                matches=tuple(matches),
            )
        status = "ambiguous" if matches else "unresolved"
        return ProviderAssetMappingResolution(
            status=status,
            provider=provider,
            provider_code=provider_code,
            observation_date=observation_date,
            matches=tuple(matches),
        )

    def _validate(self, request: RegisterAssetRequest) -> None:
        errors: list[str] = []
        if request.market not in SUPPORTED_MARKETS:
            errors.append("market")
        if request.asset_type not in SUPPORTED_ASSET_TYPES:
            errors.append("asset_type")
        if not request.exchange.strip():
            errors.append("exchange")
        elif len(request.exchange) > 64:
            errors.append("exchange")
        if not request.local_code.strip():
            errors.append("local_code")
        elif len(request.local_code) > 64:
            errors.append("local_code")
        if not request.name.strip():
            errors.append("name")
        elif len(request.name) > 256:
            errors.append("name")
        import pycountry

        if (
            len(request.trading_currency) != 3
            or not request.trading_currency.isalpha()
            or not request.trading_currency.isupper()
            or pycountry.currencies.get(alpha_3=request.trading_currency) is None
        ):
            errors.append("trading_currency")
        if request.lifecycle_status not in SUPPORTED_LIFECYCLE_STATUSES:
            errors.append("lifecycle_status")
        if request.effective_to is not None and request.effective_to < request.effective_from:
            errors.append("effective_to")
        if errors:
            raise AssetRecordValidationError(fields=errors)

    def _validate_provider_mapping(self, mapping: ProviderAssetMapping) -> None:
        errors: list[str] = []
        if not mapping.provider.strip():
            errors.append("provider")
        if not mapping.provider_code.strip():
            errors.append("provider_code")
        if len(mapping.provider_code) > 128:
            errors.append("provider_code")
        if self._repository.find(mapping.asset_id) is None:
            errors.append("asset_id")
        if mapping.effective_to is not None and mapping.effective_to < mapping.effective_from:
            errors.append("effective_to")
        if errors:
            raise AssetRecordValidationError(fields=errors)

    def _close(self, existing: AssetVersion, effective_from: date) -> None:
        del existing, effective_from

    def _create(
        self,
        request: RegisterAssetRequest,
        identity: AssetIdentity,
        asset_id: str,
        effective_from: date,
        predecessor_id: str | None,
    ) -> AssetVersion:
        record = AssetVersion(
            version_id=uuid4().hex,
            asset_id=asset_id,
            identity=identity,
            name=request.name,
            trading_currency=request.trading_currency,
            lifecycle_status=request.lifecycle_status,
            effective_from=effective_from,
            effective_to=request.effective_to,
            predecessor_id=predecessor_id,
        )
        return self._repository.create(record)
