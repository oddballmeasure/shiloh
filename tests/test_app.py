from __future__ import annotations

from collections import Counter

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
    UserRole,
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


class BrokenUsersCollection:
    async def find_one(self, filters):
        return None

    async def insert_one(self, document):
        raise RuntimeError("database unavailable")


class BrokenAuthDatabase(FakeDatabase):
    def __init__(self) -> None:
        super().__init__()
        self.users = BrokenUsersCollection()


def make_client(*, ai_service=None, database=None) -> TestClient:
    settings = Settings(
        jwt_secret="test-secret-with-at-least-thirty-two-bytes",
        internal_auth_secret="internal-secret-with-at-least-thirty-two-bytes",
        openai_api_key="",
    )
    app = create_app(
        settings=settings,
        database=database or FakeDatabase(),
        ai_service=ai_service or FakeAIService(),
        file_storage=FakeFileStorage(),
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


def test_discord_sync_stores_email_and_profile_snapshot() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")

        assert learner["user"]["role"] == "learner"
        assert learner["user"]["email"] == "discord-learner@example.com"
        assert learner["user"]["discord_profile_snapshot"]["locale"] == "en-US"


def test_health_and_readiness_checks_are_available() -> None:
    with make_client() as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {"status": "ready"}


def test_discord_sync_failures_return_readable_errors() -> None:
    with make_client(database=BrokenAuthDatabase()) as client:
        response = client.post(
            "/internal/auth/sync",
            headers={
                "x-internal-auth-secret": "internal-secret-with-at-least-thirty-two-bytes"
            },
            json={
                "discord_id": "discord-learner",
                "email": "discord-learner@example.com",
                "username": "Learner",
                "avatar_url": "https://cdn.example.com/discord-learner.png",
                "discord_profile_snapshot": {"id": "discord-learner"},
            },
        )

        assert response.status_code == 503, response.text
        assert (
            response.json()["detail"]
            == "Unable to synchronize your Discord account right now. Please try again shortly."
        )


def test_flashcard_sets_complete_and_reopen_based_on_difficulty() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        set_response = client.post(
            "/api/flashcard-sets",
            headers=auth_headers(token),
            json={
                "name": "Unit 1",
                "description": "Intro vocabulary",
                "tags": ["lesson-1", "nouns"],
            },
        )
        flashcard_set = set_response.json()

        card_one = client.post(
            f"/api/flashcard-sets/{flashcard_set['id']}/flashcards",
            headers=auth_headers(token),
            json={
                "korean": "사과",
                "english": "apple",
                "difficulty": "medium",
                "tags": ["nouns"],
            },
        ).json()
        card_two = client.post(
            f"/api/flashcard-sets/{flashcard_set['id']}/flashcards",
            headers=auth_headers(token),
            json={
                "korean": "학교",
                "english": "school",
                "difficulty": "hard",
                "tags": ["lesson-1"],
            },
        ).json()

        client.post(
            f"/api/flashcards/{card_one['id']}/review",
            headers=auth_headers(token),
            json={"difficulty": "easy"},
        )
        client.post(
            f"/api/flashcards/{card_two['id']}/review",
            headers=auth_headers(token),
            json={"difficulty": "easy"},
        )

        sets = client.get("/api/flashcard-sets", headers=auth_headers(token)).json()
        assert sets[0]["status"] == "done"

        client.patch(
            f"/api/flashcards/{card_two['id']}",
            headers=auth_headers(token),
            json={"difficulty": "hard"},
        )
        reopened_sets = client.get(
            "/api/flashcard-sets", headers=auth_headers(token)
        ).json()
        assert reopened_sets[0]["status"] == "active"


def test_study_session_weights_hard_cards_more_heavily() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        set_id = client.post(
            "/api/flashcard-sets",
            headers=auth_headers(token),
            json={"name": "Weighting", "tags": []},
        ).json()["id"]

        difficulty_map = {}
        for korean, difficulty in [
            ("어렵다", "hard"),
            ("보통", "medium"),
            ("쉽다", "easy"),
        ]:
            card = client.post(
                f"/api/flashcard-sets/{set_id}/flashcards",
                headers=auth_headers(token),
                json={
                    "korean": korean,
                    "english": korean,
                    "difficulty": difficulty,
                },
            ).json()
            difficulty_map[card["id"]] = difficulty

        first_card_counts: Counter[str] = Counter()
        for _ in range(200):
            response = client.post(
                f"/api/flashcard-sets/{set_id}/study-session",
                headers=auth_headers(token),
                json={"limit": 3},
            )
            assert response.status_code == 200, response.text
            first_card_id = response.json()["flashcards"][0]["id"]
            first_card_counts[difficulty_map[first_card_id]] += 1

        assert (
            first_card_counts["hard"]
            > first_card_counts["medium"]
            > first_card_counts["easy"]
        )


def test_manual_assignments_can_be_completed_and_scored() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]
        assignment = create_manual_assignment(client, token)

        response = client.post(
            f"/api/assignments/{assignment['id']}/submit",
            headers=auth_headers(token),
            json={
                "answers": [
                    {"question_id": assignment["questions"][0]["id"], "answer": "은"},
                    {
                        "question_id": assignment["questions"][1]["id"],
                        "answer": "안녕하세요",
                    },
                ]
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["score"] == 1.0
        assert all(item["is_correct"] for item in payload["graded_answers"])


def test_completed_assignments_can_be_reopened_with_ordered_attempt_history() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]
        assignment = create_manual_assignment(client, token)
        answers = [
            {"question_id": assignment["questions"][0]["id"], "answer": "은"},
            {"question_id": assignment["questions"][1]["id"], "answer": "안녕하세요"},
        ]

        first_attempt = client.post(
            f"/api/assignments/{assignment['id']}/submit",
            headers=auth_headers(token),
            json={"answers": answers},
        )
        assert first_attempt.status_code == 200, first_attempt.text

        reopened = client.post(
            f"/api/assignments/{assignment['id']}/redo",
            headers=auth_headers(token),
        )
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["status"] == "ready"
        assert reopened.json()["completed_at"] is None
        assert len(reopened.json()["attempts"]) == 1

        not_completed = client.post(
            f"/api/assignments/{assignment['id']}/redo",
            headers=auth_headers(token),
        )
        assert not_completed.status_code == 400, not_completed.text
        assert (
            not_completed.json()["detail"]
            == "Only completed assignments can be reopened."
        )

        second_attempt = client.post(
            f"/api/assignments/{assignment['id']}/submit",
            headers=auth_headers(token),
            json={"answers": answers},
        )
        assert second_attempt.status_code == 200, second_attempt.text

        detail = client.get(
            f"/api/assignments/{assignment['id']}", headers=auth_headers(token)
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == "completed"
        assert len(detail.json()["attempts"]) == 2
        assert detail.json()["latest_attempt"]["id"] == second_attempt.json()["id"]


def test_assignment_grading_failures_return_readable_errors() -> None:
    with make_client(ai_service=GradeFailingAIService()) as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]
        assignment = create_manual_assignment(client, token)

        response = client.post(
            f"/api/assignments/{assignment['id']}/submit",
            headers=auth_headers(token),
            json={
                "answers": [
                    {"question_id": assignment["questions"][0]["id"], "answer": "은"},
                    {
                        "question_id": assignment["questions"][1]["id"],
                        "answer": "안녕하세요",
                    },
                ]
            },
        )

        assert response.status_code == 502, response.text
        assert (
            response.json()["detail"]
            == "Assignment grading failed. Grading service unavailable."
        )


def test_ai_text_assignments_are_generated_and_ready_for_review() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        response = client.post(
            "/api/assignments/generate",
            headers=auth_headers(token),
            json={
                "title": "Cafe Phrases",
                "target_level": "beginner",
                "source_text": "카페에서 커피를 주문합니다. 친구와 인사합니다.",
            },
        )
        assert response.status_code == 201, response.text
        assignment = response.json()
        assert assignment["status"] == "processing"
        assert assignment["source"] == "ai_text"
        detail = client.get(
            f"/api/assignments/{assignment['id']}",
            headers=auth_headers(token),
        ).json()
        assert detail["status"] == "ready"


def test_pdf_assignments_store_and_serve_source_files() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        response = client.post(
            "/api/assignments/generate-from-pdf",
            headers=auth_headers(token),
            data={
                "title": "PDF Lesson",
                "target_level": "beginner",
                "study_context": "Focus on greetings.",
            },
            files={
                "file": (
                    "lesson.pdf",
                    b"%PDF-1.4 fake lesson content",
                    "application/pdf",
                ),
            },
        )
        assert response.status_code == 201, response.text
        assignment = response.json()
        assert assignment["status"] == "processing"
        assert assignment["source"] == "ai_pdf"
        assert assignment["source_file"]["filename"] == "lesson.pdf"
        detail = client.get(
            f"/api/assignments/{assignment['id']}",
            headers=auth_headers(token),
        ).json()
        assert detail["status"] == "ready"
        assert detail["source_extraction_method"] == "pymupdf4llm"

        file_response = client.get(
            f"/api/assignments/{assignment['id']}/source-file",
            headers=auth_headers(token),
        )
        assert file_response.status_code == 200, file_response.text
        assert file_response.content.startswith(b"%PDF-1.4")

        client.delete(
            f"/api/assignments/{assignment['id']}",
            headers=auth_headers(token),
        )
        assert (
            assignment["source_file"]["id"] not in client.app.state.file_storage._files
        )  # type: ignore[attr-defined]


def test_assignment_generation_failures_are_tracked_on_the_assignment() -> None:
    with make_client(ai_service=FailingAIService()) as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        response = client.post(
            "/api/assignments/generate",
            headers=auth_headers(token),
            json={
                "title": "Broken Generation",
                "target_level": "beginner",
                "source_text": "카페에서 주문합니다.",
            },
        )
        assert response.status_code == 201, response.text
        assignment = response.json()

        detail = client.get(
            f"/api/assignments/{assignment['id']}",
            headers=auth_headers(token),
        ).json()

        assert detail["status"] == "failed"
        assert detail["generation_error"] == "Model output could not be parsed."
        assert detail["generation_failed_at"] is not None
        assert len(detail["generation_failures"]) == 1
        assert detail["generation_failures"][0]["stage"] == "generation"
        assert (
            detail["generation_failures"][0]["message"]
            == "Model output could not be parsed."
        )


def test_super_admin_can_promote_admin_and_admin_can_deactivate_users() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")
        moderator = sync_user(client, "discord-moderator", "Moderator")
        root = sync_user(client, "discord-root", "Root")

        set_user_role(
            client, user_id=root["user"]["id"], role=UserRole.super_admin.value
        )
        root = sync_user(client, "discord-root", "Root")

        promote_response = client.post(
            f"/api/admin/users/{moderator['user']['id']}/promote-admin",
            headers=auth_headers(root["access_token"]),
        )
        assert promote_response.status_code == 200, promote_response.text
        assert promote_response.json()["role"] == "admin"
        moderator = sync_user(client, "discord-moderator", "Moderator")

        demote_forbidden = client.post(
            f"/api/admin/users/{root['user']['id']}/demote-admin",
            headers=auth_headers(root["access_token"]),
        )
        assert demote_forbidden.status_code == 400

        deactivate_response = client.post(
            f"/api/admin/users/{learner['user']['id']}/deactivate",
            headers=auth_headers(moderator["access_token"]),
        )
        assert deactivate_response.status_code == 200, deactivate_response.text

        profile_response = client.get(
            "/api/profile",
            headers=auth_headers(learner["access_token"]),
        )
        assert profile_response.status_code == 403
