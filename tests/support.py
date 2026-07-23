from __future__ import annotations

from fastapi.testclient import TestClient

from shiloh.config import Settings
from shiloh.main import create_app
from shiloh.schemas import (
    AssignmentGenerationPayload,
    AssignmentGradeDecision,
    AssignmentGradePayload,
    AssignmentQuestionInput,
    FlashcardCreate,
    FlashcardSetGenerationPayload,
    QuestionType,
)

from .fakes import FakeDatabase, FakeFileStorage


class FakePDFService:
    async def extract(self, *, file_bytes: bytes, filename: str):
        return type(
            "ExtractedPDF",
            (),
            {
                "markdown": "# Lesson\n안녕하세요\n사과\n학교",
                "method": "pymupdf4llm",
                "summary": {
                    "character_count": 16,
                    "line_count": 4,
                    "used_ocr_fallback": False,
                    "filename": filename,
                    "byte_count": len(file_bytes),
                },
            },
        )()


class FakeAIService:
    async def generate_assignment(self, request):
        return AssignmentGenerationPayload(
            instructions="Answer with the source material.",
            questions=[
                AssignmentQuestionInput(
                    id="generated-mc",
                    type=QuestionType.multiple_choice,
                    prompt=f"Select a Korean word related to {request.title}.",
                    options=["안녕하세요", "사과", "학교"],
                    correct_answer="안녕하세요",
                    accepted_answers=["안녕하세요"],
                ),
                AssignmentQuestionInput(
                    id="generated-short",
                    type=QuestionType.short_answer,
                    prompt="Write a short Korean greeting.",
                    correct_answer="안녕하세요",
                    accepted_answers=["안녕하세요", "안녕"],
                ),
            ],
        )

    async def grade_assignment(self, assignment, submission):
        answer_map = {
            answer.question_id: answer.answer for answer in submission.answers
        }
        graded_answers: list[AssignmentGradeDecision] = []
        for question in assignment.questions:
            normalized_answers = {
                value.strip().lower() for value in question.accepted_answers
            }
            user_answer = answer_map[question.id].strip().lower()
            is_correct = user_answer in normalized_answers
            graded_answers.append(
                AssignmentGradeDecision(
                    question_id=question.id,
                    expected_answer=question.correct_answer,
                    is_correct=is_correct,
                    score=1.0 if is_correct else 0.0,
                    feedback="Accepted." if is_correct else "Try again.",
                )
            )
        return AssignmentGradePayload(
            overall_feedback="Strong work.",
            graded_answers=graded_answers,
        )

    async def generate_flashcard_set(self, request):
        return FlashcardSetGenerationPayload(
            description=request.description
            or f"AI-enriched flashcard set for {request.name}.",
            tags=["imported", "vocabulary"],
            flashcards=[
                FlashcardCreate(
                    korean=card.korean,
                    english=card.english,
                    difficulty="medium",
                    tags=["vocabulary"],
                    notes=f"Review how '{card.english}' is used in context.",
                    example=f"오늘은 {card.korean}를 연습해요.",
                )
                for card in request.flashcards
            ],
        )


class FailingAIService:
    async def generate_assignment(self, request):
        raise RuntimeError("Model output could not be parsed.")

    async def grade_assignment(self, assignment, submission):
        raise RuntimeError("Grading service unavailable.")

    async def generate_flashcard_set(self, request):
        raise RuntimeError("Model output could not be parsed.")


class GradeFailingAIService(FakeAIService):
    async def grade_assignment(self, assignment, submission):
        raise RuntimeError("Grading service unavailable.")


def make_client(*, ai_service=None, database=None, file_storage=None) -> TestClient:
    settings = Settings(
        jwt_secret="test-secret-with-at-least-thirty-two-bytes",
        internal_auth_secret="internal-secret-with-at-least-thirty-two-bytes",
        openai_api_key="",
    )
    app = create_app(
        settings=settings,
        database=database or FakeDatabase(),
        ai_service=ai_service or FakeAIService(),
        file_storage=file_storage or FakeFileStorage(),
        pdf_service=FakePDFService(),
    )
    return TestClient(app)


def sync_user(client: TestClient, discord_id: str, username: str) -> dict:
    response = client.post(
        "/internal/auth/sync",
        headers={
            "x-internal-auth-secret": "internal-secret-with-at-least-thirty-two-bytes"
        },
        json={
            "discord_id": discord_id,
            "email": f"{discord_id}@example.com",
            "username": username,
            "avatar_url": f"https://cdn.example.com/{discord_id}.png",
            "discord_profile_snapshot": {
                "id": discord_id,
                "username": username,
                "email": f"{discord_id}@example.com",
                "locale": "en-US",
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def set_user_role(client: TestClient, *, user_id: str, role: str) -> None:
    for document in client.app.state.db.users._documents:  # type: ignore[attr-defined]
        if str(document["_id"]) == user_id:
            document["role"] = role
            return
    raise AssertionError(f"User {user_id} not found in fake database")


def create_manual_assignment(client: TestClient, token: str) -> dict:
    response = client.post(
        "/api/assignments",
        headers=auth_headers(token),
        json={
            "title": "Particles Practice",
            "instructions": "Choose the best answer.",
            "target_level": "beginner",
            "questions": [
                {
                    "type": "multiple_choice",
                    "prompt": "Choose the subject marker.",
                    "options": ["은", "를", "에"],
                    "correct_answer": "은",
                    "accepted_answers": ["은"],
                    "explanation": "은/는 marks the topic.",
                },
                {
                    "type": "short_answer",
                    "prompt": "Translate 'hello' to Korean.",
                    "correct_answer": "안녕하세요",
                    "accepted_answers": ["안녕하세요", "안녕"],
                    "explanation": "A polite greeting is acceptable.",
                },
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
