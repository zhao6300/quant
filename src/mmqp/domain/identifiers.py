from __future__ import annotations

import os
import time
from typing import NewType
from uuid import UUID

CanonicalAssetID = NewType("CanonicalAssetID", str)
ContentID = NewType("ContentID", str)
OperationID = NewType("OperationID", str)


def new_operation_id() -> OperationID:
    timestamp_ms = int(time.time() * 1000)
    random_bytes = os.urandom(10)
    identifier = bytearray(timestamp_ms.to_bytes(6, "big") + random_bytes)
    identifier[6] = (identifier[6] & 0x0F) | 0x70
    identifier[8] = (identifier[8] & 0x3F) | 0x80
    return OperationID(str(UUID(bytes=bytes(identifier))))


def validate_content_id(value: str) -> ContentID:
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValueError("invalid content ID")
    try:
        int(value[7:], 16)
    except ValueError as error:
        raise ValueError("content ID is not hexadecimal") from error
    return ContentID(value.lower())
