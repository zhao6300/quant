from __future__ import annotations

from datetime import date
from decimal import Decimal

import pyarrow as pa


def daily_bar_schema() -> pa.Schema:
    return pa.schema(
        [
            ("canonical_asset_id", pa.string()),
            ("trading_date", pa.date32()),
            ("open", pa.decimal128(18, 8)),
            ("high", pa.decimal128(18, 8)),
            ("low", pa.decimal128(18, 8)),
            ("close", pa.decimal128(18, 8)),
            ("volume", pa.int64()),
            ("provider", pa.string()),
            ("provider_code", pa.string()),
            ("available_at", pa.timestamp("us", tz="UTC")),
            ("retrieved_at", pa.timestamp("us", tz="UTC")),
            ("provenance_id", pa.string()),
            ("content_id", pa.string()),
        ]
    )


def daily_bar_table(
    content_id: str,
    provider: str,
    provider_code: str,
    available_at: str,
    retrieved_at: str,
    provenance_id: str,
    canonical_asset_id: str = "ASSET-A",
) -> pa.Table:
    return pa.Table.from_pylist(
        [
            {
                "canonical_asset_id": canonical_asset_id,
                "trading_date": date(2024, 3, 1),
                "open": Decimal("100"),
                "high": Decimal("200"),
                "low": Decimal("50"),
                "close": Decimal("150"),
                "volume": 1000,
                "provider": provider,
                "provider_code": provider_code,
                "available_at": available_at,
                "retrieved_at": retrieved_at,
                "provenance_id": provenance_id,
                "content_id": content_id,
            }
        ],
        schema=daily_bar_schema(),
    )
