from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from mmqp.adapters.parquet.content_store import ParquetContentStore


def test_published_object_is_content_addressed_and_reproducible(tmp_path: Path) -> None:
    table = pa.Table.from_pydict(
        {"id": [1], "value": [Decimal("1")], "timestamp": [1]},
        schema=pa.schema(
            [
                ("id", pa.int64()),
                ("value", pa.decimal128(2, 1)),
                ("timestamp", pa.timestamp("us", tz="UTC")),
            ]
        ),
    )
    store = ParquetContentStore(tmp_path)
    first, first_manifest = store.publish(table)
    second, second_manifest = store.publish(table)
    table = pq.read_table(first)
    assert first == second
    assert first_manifest.content_id == second_manifest.content_id
    assert table.num_rows == first_manifest.row_count
