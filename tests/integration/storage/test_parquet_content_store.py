from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from mmqp.adapters.parquet.content_store import ParquetContentStore


def test_content_store_publishes(tmp_path: Path) -> None:
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
    table = table.replace_schema_metadata({"schema_version": "arbitrary"})
    target, manifest = store.publish(table)

    restored = pq.read_table(target)
    assert restored.num_rows == 1
    assert manifest.row_count == 1
    assert manifest.artifact_path == target
    assert target.parent.parent == tmp_path
