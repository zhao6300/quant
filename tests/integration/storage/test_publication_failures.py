from pathlib import Path

import pyarrow as pa

from mmqp.adapters.parquet.content_store import ParquetContentStore


def test_publish_rollback_keeps_previous_store(tmp_path: Path) -> None:
    store = ParquetContentStore(tmp_path)
    table = pa.Table.from_pydict({"a": [1], "b": ["x"]})
    target, manifest = store.publish(table)
    store.remove(manifest.content_id)
    assert not target.exists()
