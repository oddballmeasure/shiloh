from __future__ import annotations

from fastapi import APIRouter, Depends

from shiloh.dependencies import get_current_user, get_database
from shiloh.schemas import (
    AssignmentSource,
    AssignmentStatus,
    FlashcardDifficulty,
    FlashcardSetStatus,
    ProfileSummary,
    UserResponse,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileSummary)
async def get_profile_summary(
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> ProfileSummary:
    owner_id = user["id"]
    words_learned = await db.flashcards.count_documents(
        {"owner_id": owner_id, "difficulty": FlashcardDifficulty.easy.value}
    )
    flashcard_count = await db.flashcards.count_documents({"owner_id": owner_id})
    flashcard_set_count = await db.flashcard_sets.count_documents(
        {"owner_id": owner_id}
    )
    done_set_count = await db.flashcard_sets.count_documents(
        {"owner_id": owner_id, "status": FlashcardSetStatus.done.value}
    )
    assignments_generated = await db.assignments.count_documents(
        {
            "owner_id": owner_id,
            "source": {
                "$in": [AssignmentSource.ai_text.value, AssignmentSource.ai_pdf.value]
            },
        }
    )
    assignments_manual = await db.assignments.count_documents(
        {"owner_id": owner_id, "source": AssignmentSource.manual.value}
    )
    assignments_completed = await db.assignments.count_documents(
        {"owner_id": owner_id, "status": AssignmentStatus.completed.value}
    )
    return ProfileSummary(
        user=UserResponse.model_validate(user),
        words_learned=words_learned,
        assignments_completed=assignments_completed,
        flashcard_count=flashcard_count,
        flashcard_set_count=flashcard_set_count,
        done_set_count=done_set_count,
        assignments_generated=assignments_generated,
        assignments_manual=assignments_manual,
    )
