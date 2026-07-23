from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from shiloh.dependencies import get_database, get_app_settings, require_internal_secret
from shiloh.schemas import (
    AuthSyncResponse,
    DiscordSyncRequest,
    UserResponse,
    UserRole,
    UserStatus,
)
from shiloh.security import create_access_token
from shiloh.utils import serialize_document, utcnow

router = APIRouter(tags=["auth"])


@router.post(
    "/internal/auth/sync",
    response_model=AuthSyncResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_secret)],
)
async def sync_discord_user(
    payload: DiscordSyncRequest,
    request: Request,
    db=Depends(get_database),
    settings=Depends(get_app_settings),
) -> AuthSyncResponse:
    now = utcnow()
    try:
        existing = await db.users.find_one({"discord_id": payload.discord_id})
        if existing:
            existing_role = existing.get("role", UserRole.learner.value)
            await db.users.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "email": payload.email,
                        "username": payload.username,
                        "avatar_url": payload.avatar_url,
                        "discord_profile_snapshot": payload.discord_profile_snapshot,
                        "role": existing_role,
                        "last_login_at": now,
                        "updated_at": now,
                    }
                },
            )
            document = await db.users.find_one({"_id": existing["_id"]})
        else:
            insert = {
                "discord_id": payload.discord_id,
                "email": payload.email,
                "username": payload.username,
                "avatar_url": payload.avatar_url,
                "discord_profile_snapshot": payload.discord_profile_snapshot,
                "role": UserRole.learner.value,
                "status": UserStatus.active.value,
                "last_login_at": now,
                "created_at": now,
                "updated_at": now,
            }
            result = await db.users.insert_one(insert)
            document = await db.users.find_one({"_id": result.inserted_id})
    except Exception as exc:  # pragma: no cover - defensive runtime path
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to synchronize your Discord account right now. Please try again shortly.",
        ) from exc
    serialized = serialize_document(document)
    token = create_access_token(user_id=serialized["id"], settings=settings)
    return AuthSyncResponse(
        access_token=token,
        user=UserResponse.model_validate(serialized),
    )
