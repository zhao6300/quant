from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.application.factors import FactorService, _winsorize_values
from mmqp.domain.factors import (
    FactorDefinition,
    FactorEvaluationRequest,
    FactorInput,
)


def _definition() -> FactorDefinition:
    return FactorDefinition(
        definition_id="price-reversal",
        version_id="v1",
        snapshot_schema_version="schema-v1",
        input_fields=("daily_bar_close",),
        primary_input_field="daily_bar_close",
        observation_window=1,
        transformations=(),
        missing_value_rule="EXCLUDE",
        extreme_value_rule="WINSORIZE",
        standardization_rule="NONE",
        neutralization_rule="NONE",
        transformation_specification_version="spec-v1",
    )


@settings(max_examples=10, deadline=None)
@given(
    values=st.lists(
        st.one_of(st.none(), st.decimals(allow_nan=False, allow_infinity=False)),
        min_size=1,
        max_size=8,
    ),
    q_lower=st.decimals(min_value=0, max_value=1),
    q_upper=st.decimals(min_value=0, max_value=1),
)
def test_winsorize_values_are_converted(
    values: list[Decimal | None], q_lower: Decimal, q_upper: Decimal
) -> None:
    values = values[:1]
    assert values
    if q_lower > q_upper:
        expected = None
    else:
        expected = _winsorize_values(values, q_lower, q_upper, 1)
    if expected is None:
        return
    assert expected[0] is None or expected[0] in values

    definition = _definition()
    actor = FactorService().evaluate(
        FactorEvaluationRequest(
            definition=definition,
            snapshot_id="snapshot-1",
            snapshot_schema_version="schema-v1",
            universe_version="universe-v1",
            factor_date=date(2025, 1, 2),
            decision_at=datetime(2025, 1, 2, 12, tzinfo=UTC),
            inputs=(
                FactorInput(
                    input_version_id="close-v1",
                    field_name="daily_bar_close",
                    canonical_asset_id="ASSET-A",
                    observation_date=date(2025, 1, 1),
                    value=Decimal("105.25"),
                    available_at=datetime(2025, 1, 1, 20, tzinfo=UTC),
                ),
            ),
        )
    )
    assert actor.values
