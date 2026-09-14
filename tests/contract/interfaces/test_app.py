from mmqp.adapters.fastapi.app import CreateWorkspaceRequest, app


def test_app_can_create():
    assert CreateWorkspaceRequest(path="/tmp/fake-workspace")
    assert app
