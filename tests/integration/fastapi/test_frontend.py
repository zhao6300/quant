from fastapi.testclient import TestClient

from mmqp.adapters.fastapi.app import app


def test_root_serves_web_console_fallback_when_build_is_absent() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "MMQP" in response.text
    assert "Not Found" not in response.text
