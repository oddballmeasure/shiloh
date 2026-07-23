from __future__ import annotations

import random
import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from shiloh.dependencies import get_current_user, get_database
from shiloh.schemas import (
    FlashcardCreate,
    FlashcardGenerationFailure,
    FlashcardDifficulty,
    FlashcardResponse,
    FlashcardReviewRequest,
    FlashcardSeedInput,
    FlashcardSetCreate,
    FlashcardSetGenerateRequest,
    FlashcardSetGenerationRequest,
    FlashcardSetResponse,
    FlashcardSetSource,
    FlashcardSetStatus,
    FlashcardSetUpdate,
    FlashcardUpdate,
    StudySessionRequest,
    StudySessionResponse,
)
from shiloh.utils import dedupe_strings, serialize_document, to_object_id, utcnow

router = APIRouter(prefix="/api", tags=["flashcards"])

DIFFICULTY_WEIGHTS = {
    FlashcardDifficulty.hard.value: 5,
    FlashcardDifficulty.medium.value: 3,
    FlashcardDifficulty.easy.value: 1,
}
FLASHCARD_SET_READY_STATUSES = {
    FlashcardSetStatus.active.value,
    FlashcardSetStatus.done.value,
}
FLASHCARD_LINE_SEPARATORS = ("\t", " - ", " : ", " = ")


async def _get_owned_set(db: Any, owner_id: str, set_id: str) -> dict[str, Any]:
    document = await db.flashcard_sets.find_one(
        {"_id": to_object_id(set_id), "owner_id": owner_id}
    )
    serialized = serialize_document(document)
    if serialized is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard set not found."
        )
    return serialized


async def _get_owned_flashcard(
    db: Any, owner_id: str, flashcard_id: str
) -> dict[str, Any]:
    document = await db.flashcards.find_one(
        {"_id": to_object_id(flashcard_id), "owner_id": owner_id}
    )
    serialized = serialize_document(document)
    if serialized is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found."
        )
    return serialized


async def _refresh_set_status(db: Any, set_id: str) -> None:
    object_id = to_object_id(set_id)
    total_cards = await db.flashcards.count_documents({"set_id": set_id})
    easy_cards = await db.flashcards.count_documents(
        {"set_id": set_id, "difficulty": FlashcardDifficulty.easy.value}
    )
    next_status = (
        FlashcardSetStatus.done.value
        if total_cards > 0 and total_cards == easy_cards
        else FlashcardSetStatus.active.value
    )
    await db.flashcard_sets.update_one(
        {"_id": object_id},
        {"$set": {"status": next_status, "updated_at": utcnow()}},
    )


def _ensure_set_ready(flashcard_set: dict[str, Any], *, action: str) -> None:
    if flashcard_set["status"] in FLASHCARD_SET_READY_STATUSES:
        return
    if flashcard_set["status"] == FlashcardSetStatus.processing.value:
        detail = f"This flashcard set is still processing. Wait for it to finish before you {action}."
    else:
        detail = f"This flashcard set failed to generate. Delete it or create a new set before you {action}."
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _validate_tags(selected_tags: list[str], available_tags: list[str]) -> None:
    invalid = sorted(set(selected_tags) - set(available_tags))
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unknown tags for this set: {', '.join(invalid)}",
        )


def _split_flashcard_line(line: str) -> tuple[str, str] | None:
    for separator in FLASHCARD_LINE_SEPARATORS:
        if separator not in line:
            continue
        parts = [item.strip() for item in line.split(separator)]
        if len(parts) != 2:
            return None
        return parts[0], parts[1]
    return None


def _parse_flashcard_source_text(source_text: str) -> list[FlashcardSeedInput]:
    parsed: list[FlashcardSeedInput] = []
    errors: list[str] = []
    for line_number, raw_line in enumerate(source_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = _split_flashcard_line(line)
        if parts is None:
            errors.append(
                f"Line {line_number} must use exactly one separator: tab, ' - ', ' : ', or ' = '."
            )
            continue
        korean, english = parts
        if not korean or not english:
            errors.append(
                f"Line {line_number} must include both a Korean term and an English definition."
            )
            continue
        if re.search(r"[가-힣]", korean) is None:
            errors.append(
                f"Line {line_number} must place the Korean term on the left side."
            )
            continue
        if re.search(r"[A-Za-z]", english) is None:
            errors.append(
                f"Line {line_number} must place the English definition on the right side."
            )
            continue
        parsed.append(FlashcardSeedInput(korean=korean, english=english))
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=errors,
        )
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=["Add at least one flashcard line before generating a set."],
        )
    return parsed


async def _record_generation_failure(
    db: Any,
    set_id: str,
    *,
    message: str,
) -> None:
    existing = serialize_document(
        await db.flashcard_sets.find_one({"_id": to_object_id(set_id)})
    )
    if existing is None:
        return
    failed_at = utcnow()
    failures = [
        *existing.get("generation_failures", []),
        FlashcardGenerationFailure(
            stage="generation",
            message=message,
            occurred_at=failed_at,
        ).model_dump(),
    ]
    await db.flashcard_sets.update_one(
        {"_id": to_object_id(set_id)},
        {
            "$set": {
                "status": FlashcardSetStatus.failed.value,
                "generation_error": message,
                "generation_failed_at": failed_at,
                "generation_failures": failures,
                "updated_at": failed_at,
            }
        },
    )


async def _process_generated_flashcard_set(
    app: Any,
    set_id: str,
    owner_id: str,
    generation_request: FlashcardSetGenerationRequest,
) -> None:
    db = app.state.db
    try:
        generated = await app.state.ai_service.generate_flashcard_set(
            generation_request
        )
        now = utcnow()
        set_tags = dedupe_strings(
            [
                *generated.tags,
                *[tag for card in generated.flashcards for tag in card.tags],
            ]
        )
        card_documents = [
            {
                "owner_id": owner_id,
                "set_id": set_id,
                "korean": card.korean,
                "english": card.english,
                "notes": card.notes,
                "example": card.example,
                "difficulty": card.difficulty,
                "tags": card.tags,
                "starred": card.starred,
                "correct_reviews": 0,
                "incorrect_reviews": 0,
                "last_reviewed_at": None,
                "created_at": now,
                "updated_at": now,
            }
            for card in generated.flashcards
        ]
        for card_document in card_documents:
            await db.flashcards.insert_one(card_document)
        total_cards = len(generated.flashcards)
        easy_cards = sum(
            1
            for card in generated.flashcards
            if card.difficulty == FlashcardDifficulty.easy.value
        )
        next_status = (
            FlashcardSetStatus.done.value
            if total_cards > 0 and total_cards == easy_cards
            else FlashcardSetStatus.active.value
        )
        await db.flashcard_sets.update_one(
            {"_id": to_object_id(set_id)},
            {
                "$set": {
                    "description": generated.description
                    or generation_request.description,
                    "tags": set_tags,
                    "status": next_status,
                    "generation_error": None,
                    "generation_failed_at": None,
                    "generation_failures": [],
                    "updated_at": now,
                }
            },
        )
    except Exception as exc:  # pragma: no cover - defensive runtime path
        await db.flashcards.delete_many({"set_id": set_id})
        await _record_generation_failure(db, set_id, message=str(exc))


def _weighted_flashcards(
    cards: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    if not cards:
        return []
    weighted_pool: list[str] = []
    index_lookup: dict[str, dict[str, Any]] = {}
    for card in cards:
        weight = DIFFICULTY_WEIGHTS[card["difficulty"]]
        weighted_pool.extend([card["id"]] * weight)
        index_lookup[card["id"]] = card
    random.shuffle(weighted_pool)
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card_id in weighted_pool:
        if card_id in seen:
            continue
        ordered.append(index_lookup[card_id])
        seen.add(card_id)
        if len(ordered) >= min(limit, len(cards)):
            break
    return ordered


@router.get("/flashcard-sets", response_model=list[FlashcardSetResponse])
async def list_flashcard_sets(
    user=Depends(get_current_user), db=Depends(get_database)
) -> list[FlashcardSetResponse]:
    cursor = db.flashcard_sets.find({"owner_id": user["id"]}).sort("updated_at", -1)
    documents = [
        FlashcardSetResponse.model_validate(item)
        for item in map(serialize_document, await cursor.to_list(length=500))
    ]
    return documents


@router.get("/flashcard-sets/{set_id}", response_model=FlashcardSetResponse)
async def get_flashcard_set(
    set_id: str,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> FlashcardSetResponse:
    document = await _get_owned_set(db, user["id"], set_id)
    return FlashcardSetResponse.model_validate(document)


@router.post(
    "/flashcard-sets",
    response_model=FlashcardSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_flashcard_set(
    payload: FlashcardSetCreate,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> FlashcardSetResponse:
    now = utcnow()
    document = {
        "owner_id": user["id"],
        "source": FlashcardSetSource.manual.value,
        "name": payload.name,
        "description": payload.description,
        "tags": payload.tags,
        "status": FlashcardSetStatus.active.value,
        "source_text": None,
        "generation_error": None,
        "generation_failed_at": None,
        "generation_failures": [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.flashcard_sets.insert_one(document)
    created = await db.flashcard_sets.find_one({"_id": result.inserted_id})
    return FlashcardSetResponse.model_validate(serialize_document(created))


@router.post(
    "/flashcard-sets/generate",
    response_model=FlashcardSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_flashcard_set(
    request: Request,
    payload: FlashcardSetGenerateRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> FlashcardSetResponse:
    seed_flashcards = _parse_flashcard_source_text(payload.source_text)
    now = utcnow()
    document = {
        "owner_id": user["id"],
        "source": FlashcardSetSource.ai_list.value,
        "name": payload.name,
        "description": payload.description,
        "tags": [],
        "status": FlashcardSetStatus.processing.value,
        "source_text": payload.source_text,
        "generation_error": None,
        "generation_failed_at": None,
        "generation_failures": [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.flashcard_sets.insert_one(document)
    created = await db.flashcard_sets.find_one({"_id": result.inserted_id})
    serialized = serialize_document(created)
    background_tasks.add_task(
        _process_generated_flashcard_set,
        request.app,
        serialized["id"],
        user["id"],
        FlashcardSetGenerationRequest(
            name=payload.name,
            description=payload.description,
            source_text=payload.source_text,
            flashcards=seed_flashcards,
        ),
    )
    return FlashcardSetResponse.model_validate(serialized)


@router.patch("/flashcard-sets/{set_id}", response_model=FlashcardSetResponse)
async def update_flashcard_set(
    set_id: str,
    payload: FlashcardSetUpdate,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> FlashcardSetResponse:
    existing = await _get_owned_set(db, user["id"], set_id)
    _ensure_set_ready(existing, action="update it")
    update_fields = payload.model_dump(exclude_none=True)
    if "tags" in update_fields:
        removed_tags = sorted(set(existing["tags"]) - set(update_fields["tags"]))
        if removed_tags:
            cursor = db.flashcards.find({"set_id": set_id, "owner_id": user["id"]})
            for card in map(serialize_document, await cursor.to_list(length=1000)):
                filtered_tags = [tag for tag in card["tags"] if tag not in removed_tags]
                await db.flashcards.update_one(
                    {"_id": to_object_id(card["id"])},
                    {"$set": {"tags": filtered_tags, "updated_at": utcnow()}},
                )
    if update_fields:
        update_fields["updated_at"] = utcnow()
        await db.flashcard_sets.update_one(
            {"_id": to_object_id(set_id), "owner_id": user["id"]},
            {"$set": update_fields},
        )
    document = await db.flashcard_sets.find_one({"_id": to_object_id(set_id)})
    return FlashcardSetResponse.model_validate(serialize_document(document))


@router.delete("/flashcard-sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flashcard_set(
    set_id: str,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> None:
    await _get_owned_set(db, user["id"], set_id)
    await db.flashcard_sets.delete_one(
        {"_id": to_object_id(set_id), "owner_id": user["id"]}
    )
    await db.flashcards.delete_many({"set_id": set_id, "owner_id": user["id"]})


@router.get(
    "/flashcard-sets/{set_id}/flashcards", response_model=list[FlashcardResponse]
)
async def list_flashcards(
    set_id: str,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> list[FlashcardResponse]:
    flashcard_set = await _get_owned_set(db, user["id"], set_id)
    _ensure_set_ready(flashcard_set, action="view its flashcards")
    cursor = db.flashcards.find({"set_id": set_id, "owner_id": user["id"]}).sort(
        "updated_at", -1
    )
    return [
        FlashcardResponse.model_validate(item)
        for item in map(serialize_document, await cursor.to_list(length=1000))
    ]


@router.post(
    "/flashcard-sets/{set_id}/flashcards",
    response_model=FlashcardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_flashcard(
    set_id: str,
    payload: FlashcardCreate,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> FlashcardResponse:
    flashcard_set = await _get_owned_set(db, user["id"], set_id)
    _ensure_set_ready(flashcard_set, action="add flashcards to it")
    _validate_tags(payload.tags, flashcard_set["tags"])
    now = utcnow()
    document = {
        "owner_id": user["id"],
        "set_id": set_id,
        "korean": payload.korean,
        "english": payload.english,
        "notes": payload.notes,
        "example": payload.example,
        "difficulty": payload.difficulty,
        "tags": payload.tags,
        "starred": payload.starred,
        "correct_reviews": 0,
        "incorrect_reviews": 0,
        "last_reviewed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.flashcards.insert_one(document)
    await _refresh_set_status(db, set_id)
    created = await db.flashcards.find_one({"_id": result.inserted_id})
    return FlashcardResponse.model_validate(serialize_document(created))


@router.patch("/flashcards/{flashcard_id}", response_model=FlashcardResponse)
async def update_flashcard(
    flashcard_id: str,
    payload: FlashcardUpdate,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> FlashcardResponse:
    flashcard = await _get_owned_flashcard(db, user["id"], flashcard_id)
    flashcard_set = await _get_owned_set(db, user["id"], flashcard["set_id"])
    _ensure_set_ready(flashcard_set, action="edit flashcards in it")
    update_fields = payload.model_dump(exclude_none=True)
    if "difficulty" in update_fields:
        update_fields["difficulty"] = str(update_fields["difficulty"])
    if "tags" in update_fields:
        _validate_tags(update_fields["tags"], flashcard_set["tags"])
    if update_fields:
        update_fields["updated_at"] = utcnow()
        await db.flashcards.update_one(
            {"_id": to_object_id(flashcard_id), "owner_id": user["id"]},
            {"$set": update_fields},
        )
        await _refresh_set_status(db, flashcard["set_id"])
    document = await db.flashcards.find_one({"_id": to_object_id(flashcard_id)})
    return FlashcardResponse.model_validate(serialize_document(document))


@router.delete("/flashcards/{flashcard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flashcard(
    flashcard_id: str,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> None:
    flashcard = await _get_owned_flashcard(db, user["id"], flashcard_id)
    flashcard_set = await _get_owned_set(db, user["id"], flashcard["set_id"])
    _ensure_set_ready(flashcard_set, action="delete flashcards from it")
    await db.flashcards.delete_one(
        {"_id": to_object_id(flashcard_id), "owner_id": user["id"]}
    )
    await _refresh_set_status(db, flashcard["set_id"])


@router.post("/flashcards/{flashcard_id}/review", response_model=FlashcardResponse)
async def review_flashcard(
    flashcard_id: str,
    payload: FlashcardReviewRequest,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> FlashcardResponse:
    flashcard = await _get_owned_flashcard(db, user["id"], flashcard_id)
    flashcard_set = await _get_owned_set(db, user["id"], flashcard["set_id"])
    _ensure_set_ready(flashcard_set, action="review flashcards in it")
    updates = {
        "difficulty": payload.difficulty,
        "last_reviewed_at": utcnow(),
        "updated_at": utcnow(),
    }
    if payload.difficulty == FlashcardDifficulty.easy:
        updates["correct_reviews"] = flashcard["correct_reviews"] + 1
    elif payload.difficulty == FlashcardDifficulty.hard:
        updates["incorrect_reviews"] = flashcard["incorrect_reviews"] + 1
    await db.flashcards.update_one(
        {"_id": to_object_id(flashcard_id), "owner_id": user["id"]},
        {"$set": updates},
    )
    await _refresh_set_status(db, flashcard["set_id"])
    document = await db.flashcards.find_one({"_id": to_object_id(flashcard_id)})
    return FlashcardResponse.model_validate(serialize_document(document))


@router.post(
    "/flashcard-sets/{set_id}/study-session", response_model=StudySessionResponse
)
async def create_study_session(
    set_id: str,
    payload: StudySessionRequest,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> StudySessionResponse:
    flashcard_set = await _get_owned_set(db, user["id"], set_id)
    _ensure_set_ready(flashcard_set, action="study it")
    cursor = db.flashcards.find({"set_id": set_id, "owner_id": user["id"]})
    cards = [serialize_document(item) for item in await cursor.to_list(length=1000)]
    weighted = _weighted_flashcards(cards, payload.limit)
    return StudySessionResponse(
        flashcards=[FlashcardResponse.model_validate(card) for card in weighted],
        set_status=flashcard_set["status"],
    )
