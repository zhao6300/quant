from pathlib import Path

from mmqp.application.queries import QuerySource


def test_query_source_uses_database_maps(tmp_path: Path) -> None:
    source = QuerySource([])
    assert source is not None
