from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shiloh.config import Settings
from shiloh.schemas import UserRole, UserStatus
from shiloh.security import decode_access_token
from shiloh.utils import serialize_document, to_object_id

bearer_scheme = HTTPBearer(auto_error=False)


async def get_database(request: Request) -> Any:
    return request.app.state.db


async def get_file_storage(request: Request) -> Any:
    return request.app.state.file_storage


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


async def require_internal_secret(
    request: Request,
    x_internal_auth_secret: str = Header(default=""),
) -> None:
    settings = get_app_settings(request)
    if x_internal_auth_secret != settings.internal_auth_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal auth secret.",
        )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
        )
    settings = get_app_settings(request)
    payload = decode_access_token(credentials.credentials, settings)
    user = await request.app.state.db.users.find_one(
        {"_id": to_object_id(payload["sub"])}
    )
    serialized = serialize_document(user)
    if serialized is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user not found.",
        )
    if serialized["status"] == UserStatus.deactivated.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated.",
        )
    return serialized


async def require_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if user["role"] not in {UserRole.admin.value, UserRole.super_admin.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


async def require_super_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if user["role"] != UserRole.super_admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required.",
        )
    return user
