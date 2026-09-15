from mmqp.application.assistant import AssistantContext, AssistantRequest
from mmqp.application.assistant import ResearchAssistantService


def __base_context():
    return AssistantContext(page_id="overview", source_id="sina-finance")


def _request(message: str, page_id: str, source_id: str):
    return AssistantRequest(
        message=message,
        context=AssistantContext(page_id=page_id, source_id=source_id, history_days=30),
    )


def test_assistant_routes_market_history_message_to_quote_action() -> None:
    response = ResearchAssistantService().respond(
        _request("帮我查看浦发银行最近30天K线", "overview", "sina-finance")
    )

    assert response.provider == "deterministic-intent"
    assert response.actions[0].kind == "goto_quote"
    assert response.actions[0].params["history_days"] == 30


def test_assistant_routes_data_message_to_data_action() -> None:
    response = ResearchAssistantService().respond(
        _request("查询股票基本面数据", "overview", "sina-finance")
    )

    assert response.actions[0].kind == "goto_data"
    assert response.actions[0].params["dataset"] == "FUNDAMENTAL_FACT"
    assert response.actions[0].params["field"] == "asset_type"


def test_assistant_marks_research_run_action_for_confirmation() -> None:
    response = ResearchAssistantService().respond(
        _request("我要提交一个回测", "overview", "sina-finance")
    )

    assert response.actions[0].kind == "goto_backtest"
    assert response.actions[0].confirmation_required is True
    assert response.context_used.page_id == __base_context().page_id
