from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from mmqp.domain.attribution import LinkedAttribution, build_period_attribution, linked_attribution


def compute_period_attribution(*args: Any) -> Any:
    return build_period_attribution(*args)


def compute_linked_attribution(
    periods: Sequence[tuple[Decimal, Mapping[str, Decimal]]],
) -> LinkedAttribution:
    return linked_attribution(periods)
