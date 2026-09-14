from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from mmqp.domain.identifiers import new_operation_id, validate_content_id
from mmqp.domain.intervals import InclusiveDateInterval
from mmqp.domain.numeric import aware_utc_timestamp, canonical_decimal, decimal_string
from mmqp.domain.serialization import canonical_json


def test_operation_ids_are_unique_uuid_v7() -> None:
    first = new_operation_id()
    second = new_operation_id()

    assert first != second
    assert first[14] == "7"
    assert first[19] in "89ab"


def test_content_ids_are_lowercase_sha256() -> None:
    content = validate_content_id("sha256:" + "A" * 64)

    assert content == "sha256:" + "a" * 64


def test_aware_timestamps_normalize_to_utc() -> None:
    offset_five = timezone(timedelta(hours=5))

    assert aware_utc_timestamp(datetime(2024, 5, 1, 8, tzinfo=offset_five)) == datetime(
        2024, 5, 1, 3, tzinfo=UTC
    )
    with pytest.raises(ValueError):
        aware_utc_timestamp(datetime(2024, 5, 1, 8))


def test_intervals_are_inclusive_and_bidirectional_for_overlap() -> None:
    open_ended = InclusiveDateInterval(effective_from=date(2024, 1, 1), effective_to=None)
    bounded = InclusiveDateInterval(effective_from=date(2024, 2, 1), effective_to=date(2024, 2, 28))

    assert open_ended.contains(date(2024, 2, 15))
    assert not bounded.contains(date(2024, 3, 1))
    assert open_ended.overlaps(bounded) and bounded.overlaps(open_ended)


def test_decimal_policy_rejects_null_overflow_and_precision_loss() -> None:
    exact = canonical_decimal(
        Decimal("12.25000000"),
        precision=28,
        scale=8,
        lower_bound=Decimal(0),
        upper_bound=Decimal(100),
    )

    assert decimal_string(exact) == "12.25000000"
    with pytest.raises(ValueError):
        canonical_decimal(Decimal("NaN"))
    with pytest.raises(ValueError):
        canonical_decimal(Decimal("100.01"), upper_bound=Decimal(100))
    with pytest.raises(ValueError):
        canonical_decimal(Decimal("12.250000011"))


def test_canonical_json_is_stable_and_uses_canonical_decimal_strings() -> None:
    first = canonical_json({"b": Decimal("1.250"), "a": datetime(2024, 5, 1, 5, tzinfo=UTC)})
    second = canonical_json({"a": datetime(2024, 5, 1, 5, tzinfo=UTC), "b": Decimal("1.250")})

    assert first == second == '{"a":"2024-05-01T05:00:00+00:00","b":"1.250"}'
