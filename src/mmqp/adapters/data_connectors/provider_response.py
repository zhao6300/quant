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


def fact_envelope(
    provider_name: str,
    canonical_asset_id: str,
    metric_name: str,
    source_url: str,
) -> ProviderResponseEnvelopeV1:
    return ProviderResponseEnvelopeV1(
        provider_name=provider_name,
        request_category="fundamental-fact",
        request_parameters=ProviderRequest(
            provider_name=provider_name,
            request_category="fundamental-fact",
            parameters={
                "canonical_asset_id": canonical_asset_id,
                "metric_name": metric_name,
                "source": source_url,
            },
        ).parameters,
        retrieval_time=datetime.now(UTC),
        normalized=ProviderNormalizedResponseV1({"source": source_url}),
    )
