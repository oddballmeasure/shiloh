from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from shiloh.utils import to_object_id


@dataclass
class StoredFile:
    id: str
    filename: str
    size_bytes: int
    content_type: str
    sha256: str


class GridFSStorage:
    def __init__(self, database, *, bucket_name: str = "assignment_files"):
        self.bucket = AsyncIOMotorGridFSBucket(database, bucket_name=bucket_name)

    async def store_bytes(
        self,
        *,
        data: bytes,
        filename: str,
        content_type: str,
        sha256: str,
        metadata: dict[str, object],
    ) -> StoredFile:
        file_id = await self.bucket.upload_from_stream(
            filename,
            BytesIO(data),
            metadata={
                **metadata,
                "content_type": content_type,
                "sha256": sha256,
                "size_bytes": len(data),
            },
        )
        return StoredFile(
            id=str(file_id),
            filename=filename,
            size_bytes=len(data),
            content_type=content_type,
            sha256=sha256,
        )

    async def download_bytes(self, file_id: str) -> bytes:
        stream = await self.bucket.open_download_stream(to_object_id(file_id))
        return await stream.read()

    async def delete(self, file_id: str) -> None:
        await self.bucket.delete(to_object_id(file_id))
