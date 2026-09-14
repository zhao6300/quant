from __future__ import annotations

from datetime import date
from decimal import Decimal

from mmqp.domain.fx import (
    CurrencyConversion,
    FXPolicy,
    FXRate,
    FXValidationError,
    UnavailableCurrencyConversion,
    inverse_rate,
    validate_policy,
    validate_rate,
)
from mmqp.kernels.fx import convert
from mmqp.ports.fx import FXRateRepository


class FXService:
    def __init__(self, repository: FXRateRepository | None = None, policy: FXPolicy | None = None):
        self._repository = repository
        self._policy = policy

    def register_direct(self, rate: FXRate) -> tuple[FXRate, FXRate | None]:
        validate_rate(rate)
        if rate.direct_source_version_id is not None:
            raise FXValidationError(["direct_source_version_id"])
        created = self._create(rate)
        inverse = inverse_rate(created, f"{rate.version_id}-INVERSE")
        return created, self._create(inverse)

    def register_inverse(self, rate: FXRate, direct: FXRate) -> FXRate:
        if not (len(direct.target_currency) == 3 and len(direct.source_currency) == 3):
            raise FXValidationError(["direct_rate"])
        if (
            rate.source_currency != direct.target_currency
            or rate.target_currency != direct.source_currency
            or rate.rate != Decimal(1) / direct.rate
            or rate.direct_source_version_id != direct.version_id
        ):
            raise FXValidationError(["inverse_input"])
        return self._create(rate)

    def convert(
        self,
        value: Decimal,
        source_currency: str,
        valuation_date: date,
        rates: tuple[FXRate, ...],
        policy: FXPolicy,
    ) -> CurrencyConversion | UnavailableCurrencyConversion:
        validate_policy(policy)
        if len(source_currency) != 3:
            raise ValueError("source currency must be ISO")
        return convert(value, source_currency, rates, valuation_date, policy)

    def _create(self, rate: FXRate) -> FXRate:
        owned_repository = self._repository
        if owned_repository is None:
            return rate
        return owned_repository.create(rate)
