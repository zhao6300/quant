from __future__ import annotations

from datetime import UTC, datetime

from mmqp.domain.providers import (
    ProviderNormalizedResponseV1,
    ProviderRequest,
    ProviderResponseEnvelopeV1,
)


def envelope(
    name: str,
    request_identifier: str,
    origin: str,
    *,
    source_version: str | None = None,
) -> ProviderResponseEnvelopeV1:
    return ProviderResponseEnvelopeV1(
        provider_name=name,
        request_category="daily-bar",
        request_parameters=ProviderRequest(
            provider_name=name,
            request_category="daily-bar",
            parameters={"symbol": request_identifier, "origin": origin},
        ).parameters,
        retrieval_time=datetime.now(UTC),
        normalized=ProviderNormalizedResponseV1({"format": "name", "origin": origin}),
        source_version=source_version,
    )
