from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from shiloh.dependencies import (
    get_database,
    get_file_storage,
    require_admin,
    require_super_admin,
)
from shiloh.schemas import (
    AdminUserDetail,
    AdminUserListItem,
    AssignmentResponse,
    FlashcardResponse,
    FlashcardSetResponse,
    UserRole,
    UserResponse,
    UserStatus,
)
from shiloh.utils import serialize_document, to_object_id, utcnow

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _assignment_response(document: dict, db) -> AssignmentResponse:
    payload = dict(document)
    latest_attempt = await db.assignment_attempts.find_one(
        {"assignment_id": payload["id"], "owner_id": payload["owner_id"]}
    )
    payload["latest_attempt"] = serialize_document(latest_attempt)
    return AssignmentResponse.model_validate(payload)


@router.get("/users", response_model=list[AdminUserListItem])
async def list_users(
    admin=Depends(require_admin), db=Depends(get_database)
) -> list[AdminUserListItem]:
    cursor = db.users.find({}).sort("created_at", -1)
    return [
        AdminUserListItem.model_validate(item)
        for item in map(serialize_document, await cursor.to_list(length=1000))
    ]


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: str,
    admin=Depends(require_admin),
    db=Depends(get_database),
) -> AdminUserDetail:
    user_document = await db.users.find_one({"_id": to_object_id(user_id)})
    serialized_user = serialize_document(user_document)
    if serialized_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    flashcard_cursor = db.flashcard_sets.find({"owner_id": user_id}).sort(
        "updated_at", -1
    )
    flashcards_cursor = db.flashcards.find({"owner_id": user_id}).sort("updated_at", -1)
    assignment_cursor = db.assignments.find({"owner_id": user_id}).sort(
        "updated_at", -1
    )
    flashcard_sets = [
        FlashcardSetResponse.model_validate(item)
        for item in map(serialize_document, await flashcard_cursor.to_list(length=1000))
    ]
    flashcards = [
        FlashcardResponse.model_validate(item)
        for item in map(
            serialize_document, await flashcards_cursor.to_list(length=1000)
        )
    ]
    assignments = [
        await _assignment_response(item, db)
        for item in map(
            serialize_document, await assignment_cursor.to_list(length=1000)
        )
    ]
    return AdminUserDetail(
        user=UserResponse.model_validate(serialized_user),
        flashcard_sets=flashcard_sets,
        flashcards=flashcards,
        assignments=assignments,
    )


@router.post("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: str,
    admin=Depends(require_admin),
    db=Depends(get_database),
) -> UserResponse:
    await db.users.update_one(
        {"_id": to_object_id(user_id)},
        {"$set": {"status": UserStatus.deactivated.value, "updated_at": utcnow()}},
    )
    document = await db.users.find_one({"_id": to_object_id(user_id)})
    serialized = serialize_document(document)
    if serialized is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    return UserResponse.model_validate(serialized)


@router.post("/users/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_user(
    user_id: str,
    admin=Depends(require_admin),
    db=Depends(get_database),
) -> UserResponse:
    await db.users.update_one(
        {"_id": to_object_id(user_id)},
        {"$set": {"status": UserStatus.active.value, "updated_at": utcnow()}},
    )
    document = await db.users.find_one({"_id": to_object_id(user_id)})
    serialized = serialize_document(document)
    if serialized is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    return UserResponse.model_validate(serialized)


@router.get("/flashcard-sets", response_model=list[FlashcardSetResponse])
async def list_all_flashcard_sets(
    admin=Depends(require_admin),
    db=Depends(get_database),
) -> list[FlashcardSetResponse]:
    cursor = db.flashcard_sets.find({}).sort("updated_at", -1)
    return [
        FlashcardSetResponse.model_validate(item)
        for item in map(serialize_document, await cursor.to_list(length=1000))
    ]


@router.delete("/flashcard-sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_any_flashcard_set(
    set_id: str,
    admin=Depends(require_admin),
    db=Depends(get_database),
) -> None:
    await db.flashcard_sets.delete_one({"_id": to_object_id(set_id)})
    await db.flashcards.delete_many({"set_id": set_id})


async def _delete_assignment_resources(db, file_storage, assignment: dict) -> None:
    source_file = assignment.get("source_file")
    if source_file:
        try:
            await file_storage.delete(source_file["id"])
        except Exception as exc:  # pragma: no cover - defensive runtime path
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to delete the moderated assignment file right now.",
            ) from exc
    await db.assignment_attempts.delete_many({"assignment_id": assignment["id"]})
    await db.assignments.delete_one({"_id": to_object_id(assignment["id"])})


@router.get("/assignments", response_model=list[AssignmentResponse])
async def list_all_assignments(
    admin=Depends(require_admin),
    db=Depends(get_database),
) -> list[AssignmentResponse]:
    cursor = db.assignments.find({}).sort("updated_at", -1)
    return [
        await _assignment_response(item, db)
        for item in map(serialize_document, await cursor.to_list(length=1000))
    ]


@router.get("/assignments/{assignment_id}/source-file")
async def get_assignment_source_file(
    assignment_id: str,
    admin=Depends(require_admin),
    db=Depends(get_database),
    file_storage=Depends(get_file_storage),
) -> Response:
    assignment = serialize_document(
        await db.assignments.find_one({"_id": to_object_id(assignment_id)})
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found."
        )
    source_file = assignment.get("source_file")
    if not source_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source file not found."
        )
    try:
        file_bytes = await file_storage.download_bytes(source_file["id"])
    except Exception as exc:  # pragma: no cover - defensive runtime path
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to retrieve the submitted source file right now.",
        ) from exc
    return Response(
        content=file_bytes,
        media_type=source_file["content_type"],
        headers={
            "Content-Disposition": f'inline; filename="{source_file["filename"]}"'
        },
    )


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_any_assignment(
    assignment_id: str,
    admin=Depends(require_admin),
    db=Depends(get_database),
    file_storage=Depends(get_file_storage),
) -> None:
    assignment = serialize_document(
        await db.assignments.find_one({"_id": to_object_id(assignment_id)})
    )
    if assignment is None:
        return
    await _delete_assignment_resources(db, file_storage, assignment)


@router.post("/users/{user_id}/promote-admin", response_model=UserResponse)
async def promote_user_to_admin(
    user_id: str,
    super_admin=Depends(require_super_admin),
    db=Depends(get_database),
) -> UserResponse:
    document = await db.users.find_one({"_id": to_object_id(user_id)})
    serialized = serialize_document(document)
    if serialized is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    if serialized["role"] == UserRole.super_admin.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admins can only be managed from host-side tooling.",
        )
    await db.users.update_one(
        {"_id": to_object_id(user_id)},
        {"$set": {"role": UserRole.admin.value, "updated_at": utcnow()}},
    )
    updated = await db.users.find_one({"_id": to_object_id(user_id)})
    return UserResponse.model_validate(serialize_document(updated))


@router.post("/users/{user_id}/demote-admin", response_model=UserResponse)
async def demote_user_from_admin(
    user_id: str,
    super_admin=Depends(require_super_admin),
    db=Depends(get_database),
) -> UserResponse:
    document = await db.users.find_one({"_id": to_object_id(user_id)})
    serialized = serialize_document(document)
    if serialized is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    if serialized["role"] == UserRole.super_admin.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admins can only be managed from host-side tooling.",
        )
    await db.users.update_one(
        {"_id": to_object_id(user_id)},
        {"$set": {"role": UserRole.learner.value, "updated_at": utcnow()}},
    )
    updated = await db.users.find_one({"_id": to_object_id(user_id)})
    return UserResponse.model_validate(serialize_document(updated))
