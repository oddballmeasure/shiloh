from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_object_id(value: str, *, detail: str = "Invalid identifier.") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return ObjectId(value)


def dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def serialize_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return _serialize_value(document)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        cloned = deepcopy(value)
        if "_id" in cloned:
            cloned["id"] = str(cloned.pop("_id"))
        return {key: _serialize_value(item) for key, item in cloned.items()}
    return value
