from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, cast

from mmqp.domain.providers import ProviderCategorizedError


def _raw_open(url: str, timeout: float) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json,text/csv,text/html,*/*",
            "User-Agent": "Mozilla/5.0 (compatible; MMQP/0.1)",
        },
    )
    return urllib.request.urlopen(request, timeout=timeout)


class HTTPTransport:
    def __init__(
        self,
        opener: Callable[[str, float], object] | None = None,
        timeout: float = 30,
    ) -> None:
        self._opener = opener if opener is not None else _raw_open
        self.timeout = timeout

    def text(self, url: str) -> str:
        return self._content(url).decode("utf-8")

    def request(self, url: str) -> str:
        return self.text(url)

    def json(self, url: str) -> dict[str, object]:
        parsed = json.loads(self._content(url).decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}

    def _content(self, url: str) -> bytes:
        try:
            response = self._opener(url, self.timeout)
            status_value = getattr(response, "status", None)
            if not isinstance(status_value, int) and hasattr(response, "getcode"):
                status_value = response.getcode()
            if isinstance(status_value, int) and status_value >= 400:
                raise _http_error(status_value)
            return cast(bytes, cast(Any, response).read())
        except urllib.error.HTTPError as error:
            error_status = error.status if isinstance(error.status, int) else 503
            raise _http_error(error_status) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise _http_error(503) from error


def _http_error(status: int) -> ProviderCategorizedError:
    return ProviderCategorizedError(
        category="throttled" if status == 429 else "unavailable",
        provider_name="data-source",
        request_category="daily-bar",
        retry="safe_after" if status == 429 or status >= 500 else "never",
        status=status,
    )
