from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from mmqp.adapters.duckdb.engine import DuckDBReadonlyEngine


def test_engine_selects_registered_view(tmp_path: Path) -> None:
    table = pa.Table.from_pydict({"id": [1]}, schema=pa.schema([("id", pa.int64())]))
    pq.write_table(table, tmp_path / "test_table.parquet")
    engine = DuckDBReadonlyEngine(
        views={"test_table": tmp_path / "test_table.parquet"},
        limit=10,
    )
    assert engine.select(table_name="test_table", columns=["id"]).num_rows == 1
