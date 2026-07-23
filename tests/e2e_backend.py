from __future__ import annotations

from fastapi import Body

from shiloh.config import Settings
from shiloh.main import create_app
from shiloh.utils import to_object_id

from .fakes import FakeDatabase, FakeFileStorage
from .support import FakeAIService, FakePDFService

database = FakeDatabase()
file_storage = FakeFileStorage()

settings = Settings(
    jwt_secret="test-secret-with-at-least-thirty-two-bytes",
    internal_auth_secret="internal-secret-with-at-least-thirty-two-bytes",
    openai_api_key="",
    assignment_pdf_max_bytes=50 * 1024 * 1024,
)

app = create_app(
    settings=settings,
    database=database,
    ai_service=FakeAIService(),
    file_storage=file_storage,
    pdf_service=FakePDFService(),
)


@app.post("/internal/test/reset")
async def reset_test_state() -> dict[str, str]:
    database.reset()
    file_storage.reset()
    return {"status": "ok"}


@app.post("/internal/test/users/{discord_id}/role")
async def set_test_user_role(
    discord_id: str, role: str = Body(embed=True)
) -> dict[str, str]:
    user = await database.users.find_one({"discord_id": discord_id})
    if user is None:
        return {"status": "missing"}
    await database.users.update_one(
        {"_id": to_object_id(str(user["_id"]))},
        {"$set": {"role": role}},
    )
    return {"status": "ok"}
