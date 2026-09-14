import os

import pytest


@pytest.fixture
def database(tmp_path: str) -> str:
    return os.path.join(str(tmp_path), "fx.sqlite3")
