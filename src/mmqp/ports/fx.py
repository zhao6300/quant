from builtins import list as list_type
from datetime import date
from typing import Protocol

from mmqp.domain.fx import FXRate


class FXRateRepository(Protocol):
    def create(self, rate: FXRate) -> FXRate: ...
    def select(
        self,
        source_currency: str,
        target_currency: str,
        rate_dates: tuple[date, ...],
    ) -> list_type[FXRate]: ...
    def close(self) -> None: ...
