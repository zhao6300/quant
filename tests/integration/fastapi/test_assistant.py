from fastapi.testclient import TestClient

from mmqp.adapters.fastapi.app import app


def test_assistant_endpoint_responds_with_scopeously_operations() -> None:
    payload = {
        "message": "查看浦发银行最近30天行情",
        "context": {
            "page_id": "overview",
            "source_id": "sina-finance",
            "market_id": "a-share",
            "market": "A_SHARE",
            "exchange": "SSE",
            "symbol": "600000.SS",
            "trading_date": "2026-09-15",
            "history_days": 30,
        },
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/assistant/respond", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "deterministic-intent"
    assert body["context_used"]["source_id"] == "sina-finance"
    assert body["actions"][0]["kind"] == "goto_quote"
    assert body["actions"][0]["params"]["symbol"] == "600000.SS"
    assert body["actions"][0]["params"]["history_days"] == 30
