from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from bson import ObjectId


@dataclass
class InsertOneResult:
    inserted_id: ObjectId


class FakeAsyncCursor:
    def __init__(self, documents: list[dict[str, Any]]):
        self._documents = documents

    def sort(self, field: str, direction: int) -> "FakeAsyncCursor":
        reverse = direction == -1
        self._documents.sort(key=lambda item: item.get(field), reverse=reverse)
        return self

    async def to_list(self, length: int) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in self._documents[:length]]


class FakeAsyncCollection:
    def __init__(self) -> None:
        self._documents: list[dict[str, Any]] = []

    def reset(self) -> None:
        self._documents = []

    def _matches(self, document: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, value in filters.items():
            if isinstance(value, dict) and "$in" in value:
                if document.get(key) not in value["$in"]:
                    return False
                continue
            if document.get(key) != value:
                return False
        return True

    async def find_one(self, filters: dict[str, Any]) -> dict[str, Any] | None:
        for document in self._documents:
            if self._matches(document, filters):
                return deepcopy(document)
        return None

    def find(self, filters: dict[str, Any]) -> FakeAsyncCursor:
        return FakeAsyncCursor(
            [deepcopy(item) for item in self._documents if self._matches(item, filters)]
        )

    async def insert_one(self, document: dict[str, Any]) -> InsertOneResult:
        stored = deepcopy(document)
        stored["_id"] = stored.get("_id", ObjectId())
        self._documents.append(stored)
        return InsertOneResult(inserted_id=stored["_id"])

    async def update_one(self, filters: dict[str, Any], update: dict[str, Any]) -> None:
        for document in self._documents:
            if not self._matches(document, filters):
                continue
            for key, value in update.get("$set", {}).items():
                document[key] = deepcopy(value)
            for key, value in update.get("$inc", {}).items():
                document[key] = document.get(key, 0) + value
            return

    async def delete_one(self, filters: dict[str, Any]) -> None:
        for index, document in enumerate(self._documents):
            if self._matches(document, filters):
                self._documents.pop(index)
                return

    async def delete_many(self, filters: dict[str, Any]) -> None:
        self._documents = [
            document
            for document in self._documents
            if not self._matches(document, filters)
        ]

    async def count_documents(self, filters: dict[str, Any]) -> int:
        return sum(1 for item in self._documents if self._matches(item, filters))


class FakeDatabase:
    def __init__(self) -> None:
        self.users = FakeAsyncCollection()
        self.flashcard_sets = FakeAsyncCollection()
        self.flashcards = FakeAsyncCollection()
        self.assignments = FakeAsyncCollection()
        self.assignment_attempts = FakeAsyncCollection()

    def reset(self) -> None:
        self.users.reset()
        self.flashcard_sets.reset()
        self.flashcards.reset()
        self.assignments.reset()
        self.assignment_attempts.reset()

    async def command(self, command: str) -> dict[str, int]:
        if command != "ping":
            raise ValueError(f"Unsupported database command: {command}")
        return {"ok": 1}


class FakeFileStorage:
    def __init__(self) -> None:
        self._files: dict[str, dict[str, Any]] = {}

    def reset(self) -> None:
        self._files = {}

    async def store_bytes(
        self,
        *,
        data: bytes,
        filename: str,
        content_type: str,
        sha256: str,
        metadata: dict[str, object],
    ) -> Any:
        file_id = str(ObjectId())
        self._files[file_id] = {
            "data": data,
            "filename": filename,
            "content_type": content_type,
            "sha256": sha256,
            "metadata": deepcopy(metadata),
        }
        return type(
            "StoredFile",
            (),
            {
                "id": file_id,
                "filename": filename,
                "size_bytes": len(data),
                "content_type": content_type,
                "sha256": sha256,
            },
        )()

    async def download_bytes(self, file_id: str) -> bytes:
        return self._files[file_id]["data"]

    async def delete(self, file_id: str) -> None:
        self._files.pop(file_id, None)
