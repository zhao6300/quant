from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatusReport:
    platform_version: str
    provider_adapter_versions: tuple[str, ...]
    adapter_contract_versions: tuple[str, ...]
    schema_version: str
    restore_schema_versions: tuple[str, ...]
    migration: str


def status_report(source: object) -> object:
    return source
