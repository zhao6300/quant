from mmqp.domain.common import canonical_asset_id


def test_canonical_asset_id_is_idempotent_and_discriminating() -> None:
    first = canonical_asset_id("A_SHARE", "equity", "SSE", "600000")
    second = canonical_asset_id(" a_share ", "Equity", "sse", "600000")
    different = canonical_asset_id("A_SHARE", "equity", "SSE", "600001")
    assert first == second
    assert first != different
