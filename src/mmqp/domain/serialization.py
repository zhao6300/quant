from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from mmqp.domain.identifiers import validate_content_id


def canonical_json(value: Any) -> str:
    prepared = _canonical_value(value)
    return json.dumps(prepared, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_value(value: Any) -> object:
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("timestamps must be aware")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def content_id(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return validate_content_id("sha256:" + value.hex())
