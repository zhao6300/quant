from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from mmqp.domain.providers import (
    ProviderAdapterStatusV1,
    ProviderCategorizedError,
    ProviderRequest,
    ProviderResponseEnvelopeV1,
)

MAX_TIMEOUT_SECONDS = 30
ProviderTransport = Callable[[ProviderRequest], Any]


class ProviderHTTPClient:
    def __init__(
        self,
        transport: ProviderTransport,
        *,
        timeout_seconds: float = MAX_TIMEOUT_SECONDS,
    ) -> None:
        if not (0 < timeout_seconds <= MAX_TIMEOUT_SECONDS):
            raise ProviderCategorizedError(
                category="policy_blocked",
                provider_name="<unset>",
                request_category="<unset>",
            )
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    @property
    def hard_timeout_seconds(self) -> int:
        return MAX_TIMEOUT_SECONDS

    def send(
        self,
        request: ProviderRequest,
        *,
        adapter_status: ProviderAdapterStatusV1 | None = None,
        timeout_seconds: float | None = None,
    ) -> ProviderResponseEnvelopeV1:
        selected_timeout = MAX_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        if not (0 < selected_timeout <= MAX_TIMEOUT_SECONDS):
            raise self._categorized(
                request,
                category="policy_blocked",
                status=403,
            )
        if adapter_status is not None:
            self._validate_adapter(adapter_status)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._transport, request)
                response = future.result(selected_timeout)
        except TimeoutError as error:
            raise self._categorized(
                request,
                category="timeout",
                status=504,
                retry="safe_immediate",
            ) from error
        if response is None:
            raise self._categorized(
                request,
                category="invalid_response",
                status=502,
            )
        if isinstance(response, Mapping):
            status_code = response.get("status_code")
            if isinstance(status_code, int) and status_code >= 400:
                raise self._categorized(
                    request,
                    category="throttled" if status_code == 429 else "unavailable",
                    status=status_code,
                    provider_correlation_id=_text(response.get("provider_correlation_id")),
                )
        if not isinstance(response, ProviderResponseEnvelopeV1):
            raise self._categorized(
                request,
                category="invalid_response",
                status=502,
            )
        return response

    def _categorized(
        self,
        request: ProviderRequest,
        *,
        category: Literal[
            "timeout",
            "throttled",
            "unavailable",
            "invalid_response",
            "policy_blocked",
        ],
        status: int,
        retry: Literal["never", "safe_immediate", "safe_after"] = "never",
        provider_correlation_id: str | None = None,
    ) -> ProviderCategorizedError:
        return ProviderCategorizedError(
            category=category,
            provider_name=request.provider_name,
            request_category=request.request_category,
            retry=retry,
            status=status,
            provider_correlation_id=provider_correlation_id,
        )

    def _validate_adapter(self, adapter_status: ProviderAdapterStatusV1) -> None:
        capabilities = adapter_status.capabilities
        if (
            adapter_status.incompatible_reason is not None
            or not adapter_status.enabled
            or capabilities.contract_version != "1.0"
            or capabilities.normalized_response != "supported"
            or capabilities.provenance != "supported"
            or capabilities.categorized_errors != "supported"
        ):
            raise self._categorized(
                ProviderRequest(
                    provider_name=adapter_status.provider_name,
                    request_category="<unset>",
                    parameters={},
                ),
                category="policy_blocked",
                status=403,
            )


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
