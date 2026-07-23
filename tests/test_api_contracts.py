from __future__ import annotations

from fastapi.testclient import TestClient

from .fakes import FakeFileStorage
from .support import (
    FailingAIService,
    auth_headers,
    create_manual_assignment,
    make_client,
    set_user_role,
    sync_user,
)


def create_flashcard_set(client: TestClient, token: str) -> dict:
    response = client.post(
        "/api/flashcard-sets",
        headers=auth_headers(token),
        json={
            "name": "Travel Vocabulary",
            "description": "Airport and hotel basics",
            "tags": ["travel", "lesson-2"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_flashcard(client: TestClient, token: str, set_id: str) -> dict:
    response = client.post(
        f"/api/flashcard-sets/{set_id}/flashcards",
        headers=auth_headers(token),
        json={
            "korean": "공항",
            "english": "airport",
            "notes": "Useful for travel questions.",
            "example": "공항에 가요.",
            "difficulty": "hard",
            "tags": ["travel"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_ai_flashcard_set(client: TestClient, token: str) -> dict:
    response = client.post(
        "/api/flashcard-sets/generate",
        headers=auth_headers(token),
        json={
            "name": "Imported Travel Vocabulary",
            "description": "Bulk imported travel words.",
            "source_text": "공항 - airport\n호텔 - hotel",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_pdf_assignment(client: TestClient, token: str) -> dict:
    response = client.post(
        "/api/assignments/generate-from-pdf",
        headers=auth_headers(token),
        data={
            "title": "Lesson PDF",
            "target_level": "beginner",
            "study_context": "Review the lesson handout.",
        },
        files={"file": ("lesson.pdf", b"%PDF-1.4 lesson", "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_profile_flashcard_and_study_routes_support_learner_views() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        flashcard_set = create_flashcard_set(client, token)
        flashcard = create_flashcard(client, token, flashcard_set["id"])

        profile = client.get("/api/profile", headers=auth_headers(token))
        assert profile.status_code == 200, profile.text
        assert profile.json()["flashcard_set_count"] == 1

        list_sets = client.get("/api/flashcard-sets", headers=auth_headers(token))
        assert list_sets.status_code == 200, list_sets.text
        assert list_sets.json()[0]["id"] == flashcard_set["id"]

        list_cards = client.get(
            f"/api/flashcard-sets/{flashcard_set['id']}/flashcards",
            headers=auth_headers(token),
        )
        assert list_cards.status_code == 200, list_cards.text
        assert list_cards.json()[0]["id"] == flashcard["id"]
        assert list_cards.json()[0]["starred"] is False

        study_session = client.post(
            f"/api/flashcard-sets/{flashcard_set['id']}/study-session",
            headers=auth_headers(token),
            json={"limit": 20},
        )
        assert study_session.status_code == 200, study_session.text
        assert study_session.json()["flashcards"][0]["id"] == flashcard["id"]

        reviewed = client.post(
            f"/api/flashcards/{flashcard['id']}/review",
            headers=auth_headers(token),
            json={"difficulty": "easy"},
        )
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["difficulty"] == "easy"
        assert reviewed.json()["starred"] is False


def test_flashcard_mutation_routes_support_update_and_delete() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        flashcard_set = create_flashcard_set(client, token)
        flashcard = create_flashcard(client, token, flashcard_set["id"])

        updated_set = client.patch(
            f"/api/flashcard-sets/{flashcard_set['id']}",
            headers=auth_headers(token),
            json={
                "name": "Updated Travel Vocabulary",
                "description": "Updated description",
                "tags": ["travel", "dialogue", "lodging"],
            },
        )
        assert updated_set.status_code == 200, updated_set.text
        assert updated_set.json()["tags"] == ["travel", "dialogue", "lodging"]

        updated_card = client.patch(
            f"/api/flashcards/{flashcard['id']}",
            headers=auth_headers(token),
            json={
                "korean": "호텔",
                "english": "hotel",
                "notes": "Useful for lodging.",
                "example": "호텔에 묵어요.",
                "difficulty": "medium",
                "tags": ["travel", "lodging"],
                "starred": True,
            },
        )
        assert updated_card.status_code == 200, updated_card.text
        assert updated_card.json()["difficulty"] == "medium"
        assert updated_card.json()["starred"] is True

        delete_card = client.delete(
            f"/api/flashcards/{flashcard['id']}",
            headers=auth_headers(token),
        )
        assert delete_card.status_code == 204, delete_card.text

        delete_set = client.delete(
            f"/api/flashcard-sets/{flashcard_set['id']}",
            headers=auth_headers(token),
        )
        assert delete_set.status_code == 204, delete_set.text


def test_ai_flashcard_import_routes_support_generation_and_detail_polling() -> None:
    with make_client() as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        generated_set = create_ai_flashcard_set(client, token)
        assert generated_set["status"] == "processing"
        assert generated_set["source"] == "ai_list"
        assert generated_set["source_text"] == "공항 - airport\n호텔 - hotel"

        detail = client.get(
            f"/api/flashcard-sets/{generated_set['id']}",
            headers=auth_headers(token),
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == "active"
        assert detail.json()["tags"] == ["imported", "vocabulary"]
        assert detail.json()["generation_error"] is None

        cards = client.get(
            f"/api/flashcard-sets/{generated_set['id']}/flashcards",
            headers=auth_headers(token),
        )
        assert cards.status_code == 200, cards.text
        payload = cards.json()
        assert len(payload) == 2
        assert payload[0]["notes"]
        assert payload[0]["example"]
        assert payload[0]["starred"] is False


def test_ai_flashcard_import_routes_return_readable_validation_and_failure_errors() -> (
    None
):
    with make_client(ai_service=FailingAIService()) as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        invalid_import = client.post(
            "/api/flashcard-sets/generate",
            headers=auth_headers(token),
            json={
                "name": "Broken Import",
                "description": "Missing separators.",
                "source_text": "공항 airport\n호텔 - hotel - lodging",
            },
        )
        assert invalid_import.status_code == 422, invalid_import.text
        assert "Line 1 must use exactly one separator" in invalid_import.text
        assert "Line 2 must use exactly one separator" in invalid_import.text

        generated_set = client.post(
            "/api/flashcard-sets/generate",
            headers=auth_headers(token),
            json={
                "name": "Failing Import",
                "description": "AI should fail here.",
                "source_text": "공항 - airport\n호텔 - hotel",
            },
        )
        assert generated_set.status_code == 201, generated_set.text
        assert generated_set.json()["status"] == "processing"

        detail = client.get(
            f"/api/flashcard-sets/{generated_set.json()['id']}",
            headers=auth_headers(token),
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == "failed"
        assert detail.json()["generation_error"] == "Model output could not be parsed."
        assert len(detail.json()["generation_failures"]) == 1

        blocked = client.get(
            f"/api/flashcard-sets/{generated_set.json()['id']}/flashcards",
            headers=auth_headers(token),
        )
        assert blocked.status_code == 409, blocked.text
        assert "failed to generate" in blocked.json()["detail"]


def test_assignment_routes_support_text_manual_pdf_and_source_file_access() -> None:
    file_storage = FakeFileStorage()
    with make_client(file_storage=file_storage) as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        generated_text = client.post(
            "/api/assignments/generate",
            headers=auth_headers(token),
            json={
                "title": "Dialogue Builder",
                "target_level": "beginner",
                "source_text": "안녕하세요. 만나서 반갑습니다.",
                "study_context": "Focus on beginner greetings.",
            },
        )
        assert generated_text.status_code == 201, generated_text.text
        assert generated_text.json()["status"] in {"processing", "ready"}

        manual_assignment = create_manual_assignment(client, token)
        pdf_assignment = create_pdf_assignment(client, token)

        assignments = client.get("/api/assignments", headers=auth_headers(token))
        assert assignments.status_code == 200, assignments.text
        assert {item["source"] for item in assignments.json()} >= {
            "manual",
            "ai_text",
            "ai_pdf",
        }

        assignment_detail = client.get(
            f"/api/assignments/{manual_assignment['id']}",
            headers=auth_headers(token),
        )
        assert assignment_detail.status_code == 200, assignment_detail.text
        assert assignment_detail.json()["id"] == manual_assignment["id"]

        source_file = client.get(
            f"/api/assignments/{pdf_assignment['id']}/source-file",
            headers=auth_headers(token),
        )
        assert source_file.status_code == 200, source_file.text
        assert source_file.headers["content-type"] == "application/pdf"
        assert source_file.content.startswith(b"%PDF-1.4")

        submission = client.post(
            f"/api/assignments/{manual_assignment['id']}/submit",
            headers=auth_headers(token),
            json={
                "answers": [
                    {
                        "question_id": manual_assignment["questions"][0]["id"],
                        "answer": "은",
                    },
                    {
                        "question_id": manual_assignment["questions"][1]["id"],
                        "answer": "안녕하세요",
                    },
                ]
            },
        )
        assert submission.status_code == 200, submission.text
        assert submission.json()["score"] == 1.0


def test_assignment_routes_return_readable_validation_and_service_errors() -> None:
    with make_client(ai_service=FailingAIService()) as client:
        learner = sync_user(client, "discord-learner", "Learner")
        token = learner["access_token"]

        invalid_manual = client.post(
            "/api/assignments",
            headers=auth_headers(token),
            json={
                "title": "Broken Assignment",
                "instructions": "Should fail validation.",
                "target_level": "beginner",
                "questions": [
                    {
                        "type": "multiple_choice",
                        "prompt": "Pick one option.",
                        "options": ["은"],
                        "correct_answer": "은",
                        "accepted_answers": ["은"],
                    }
                ],
            },
        )
        assert invalid_manual.status_code == 422, invalid_manual.text
        assert "at least two options" in invalid_manual.json()["detail"][0]["msg"]

        invalid_pdf = client.post(
            "/api/assignments/generate-from-pdf",
            headers=auth_headers(token),
            data={"title": "Wrong File", "target_level": "beginner"},
            files={"file": ("lesson.txt", b"not a pdf", "text/plain")},
        )
        assert invalid_pdf.status_code == 415, invalid_pdf.text
        assert invalid_pdf.json()["detail"] == "Only PDF uploads are supported."

        generated = client.post(
            "/api/assignments/generate",
            headers=auth_headers(token),
            json={
                "title": "Failing Generation",
                "instructions": "Trigger the fake AI failure.",
                "target_level": "beginner",
                "source_text": "안녕하세요",
            },
        )
        assert generated.status_code == 201, generated.text
        assert generated.json()["status"] == "processing"

        assignments = client.get("/api/assignments", headers=auth_headers(token))
        failed = next(
            item for item in assignments.json() if item["title"] == "Failing Generation"
        )
        assert failed["status"] == "failed"
        assert failed["generation_error"] == "Model output could not be parsed."
        assert failed["generation_failures"][0]["stage"] == "generation"


def test_admin_routes_support_user_management_and_content_moderation() -> None:
    file_storage = FakeFileStorage()
    with make_client(file_storage=file_storage) as client:
        super_admin = sync_user(client, "discord-super-admin", "Super Admin")
        learner = sync_user(client, "discord-learner", "Learner")
        super_admin_token = super_admin["access_token"]
        learner_token = learner["access_token"]

        set_user_role(client, user_id=super_admin["user"]["id"], role="super_admin")

        flashcard_set = create_flashcard_set(client, learner_token)
        create_flashcard(client, learner_token, flashcard_set["id"])
        pdf_assignment = create_pdf_assignment(client, learner_token)

        non_admin_users = client.get(
            "/api/admin/users", headers=auth_headers(learner_token)
        )
        assert non_admin_users.status_code == 403, non_admin_users.text
        assert non_admin_users.json()["detail"] == "Admin access required."

        users = client.get("/api/admin/users", headers=auth_headers(super_admin_token))
        assert users.status_code == 200, users.text
        assert len(users.json()) == 2

        detail = client.get(
            f"/api/admin/users/{learner['user']['id']}",
            headers=auth_headers(super_admin_token),
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["user"]["discord_id"] == "discord-learner"

        deactivated = client.post(
            f"/api/admin/users/{learner['user']['id']}/deactivate",
            headers=auth_headers(super_admin_token),
        )
        assert deactivated.status_code == 200, deactivated.text
        assert deactivated.json()["status"] == "deactivated"

        blocked = client.get("/api/profile", headers=auth_headers(learner_token))
        assert blocked.status_code == 403, blocked.text
        assert blocked.json()["detail"] == "Your account has been deactivated."

        reactivated = client.post(
            f"/api/admin/users/{learner['user']['id']}/reactivate",
            headers=auth_headers(super_admin_token),
        )
        assert reactivated.status_code == 200, reactivated.text
        assert reactivated.json()["status"] == "active"

        promoted = client.post(
            f"/api/admin/users/{learner['user']['id']}/promote-admin",
            headers=auth_headers(super_admin_token),
        )
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["role"] == "admin"

        demoted = client.post(
            f"/api/admin/users/{learner['user']['id']}/demote-admin",
            headers=auth_headers(super_admin_token),
        )
        assert demoted.status_code == 200, demoted.text
        assert demoted.json()["role"] == "learner"

        admin_sets = client.get(
            "/api/admin/flashcard-sets", headers=auth_headers(super_admin_token)
        )
        assert admin_sets.status_code == 200, admin_sets.text
        assert admin_sets.json()[0]["id"] == flashcard_set["id"]

        admin_assignments = client.get(
            "/api/admin/assignments", headers=auth_headers(super_admin_token)
        )
        assert admin_assignments.status_code == 200, admin_assignments.text
        assert admin_assignments.json()[0]["id"] == pdf_assignment["id"]

        moderated_file = client.get(
            f"/api/admin/assignments/{pdf_assignment['id']}/source-file",
            headers=auth_headers(super_admin_token),
        )
        assert moderated_file.status_code == 200, moderated_file.text
        assert moderated_file.headers["content-type"] == "application/pdf"

        delete_assignment = client.delete(
            f"/api/admin/assignments/{pdf_assignment['id']}",
            headers=auth_headers(super_admin_token),
        )
        assert delete_assignment.status_code == 204, delete_assignment.text

        delete_set = client.delete(
            f"/api/admin/flashcard-sets/{flashcard_set['id']}",
            headers=auth_headers(super_admin_token),
        )
        assert delete_set.status_code == 204, delete_set.text
