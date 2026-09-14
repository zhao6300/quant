import pytest

from mmqp.adapters.provider_adapter import pre_restore_check, restoration_status


@pytest.mark.parametrize(
    ("path", "expectation"),
    [
        ("/workspace", True),
        ("/workspace/xml", False),
        ("/workspace/style.css", False),
    ],
)
def test_paths_have_sufficient_capacity(path, expectation):
    if expectation:
        assert restoration_status(path) is True
    else:
        with pytest.raises(Exception, match="state"):
            restoration_status(path)


@pytest.mark.parametrize(
    ("payload", "expectation"),
    [("key:value:true", True), ("key,value:false", False)],
)
def test_payload_gates_send(payload, expectation):
    if expectation:
        assert pre_restore_check(10_000, 0) is True
    else:
        with pytest.raises(Exception, match="provider"):
            pre_restore_check(0, 10)
