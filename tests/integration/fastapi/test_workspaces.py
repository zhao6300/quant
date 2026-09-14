from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mmqp.adapters.fastapi.app import app, get_workspace_repository
from mmqp.adapters.sqlite.workspace_repository import SqliteWorkspaceRepository


@pytest.fixture
def workspace_path(tmp_path: Path) -> Iterator[Path]:
    database = tmp_path / "workspaces.sqlite3"
    repository = SqliteWorkspaceRepository(database)
    app.dependency_overrides[get_workspace_repository] = lambda: repository
    yield tmp_path / "research"
    app.dependency_overrides.clear()


def test_status_and_workspace_creation(workspace_path: Path) -> None:
    with TestClient(app) as client:
        status = client.get("/api/v1/status")
        assert status.status_code == 200
        assert status.json()["workspace_count"] == 0

        response = client.post(
            "/api/v1/workspaces", json={"path": str(workspace_path), "display_name": "Research"}
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["display_name"] == "Research"
        assert Path(payload["path"]) == workspace_path
        assert client.get("/api/v1/status").json()["workspace_count"] == 1
        opened = client.post("/api/v1/workspaces/open", json={"path": str(workspace_path)})
        assert opened.status_code == 200
        assert opened.json()["id"] == payload["id"]
        assert (workspace_path / "workspace.toml").is_file()
        for child in ("objects", "manifests", "results", "staging", "locks", "logs", "backups"):
            assert (workspace_path / child).is_dir()
