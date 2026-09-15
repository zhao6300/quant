from __future__ import annotations

from datetime import date

import pytest
import requests

from mmqp.adapters.data_connectors.package_sources import AkShareDailyBarConnector
from mmqp.domain.providers import ProviderCategorizedError


def test_akshare_connector_categorizes_a_request_failure() -> None:
    class _FakeAkShare:
        def stock_zh_a_hist(self, *_args, **_kwargs):
            raise requests.ConnectionError("Remote end closed connection")

    with pytest.raises(ProviderCategorizedError) as error:
        AkShareDailyBarConnector(_FakeAkShare()).fetch(
            provider_code="600000.SS",
            trading_date=date(2026, 9, 14),
        )

    assert error.value.category == "unavailable"
    assert error.value.provider_name == "akshare"
    assert error.value.problem.status == 503
