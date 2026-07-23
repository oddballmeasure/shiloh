from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from shiloh.config import Settings
from shiloh.schemas import (
    AssignmentGenerateTextRequest,
    AssignmentGenerationPayload,
    AssignmentQuestionResponse,
    AssignmentResponse,
    AssignmentSource,
    AssignmentStatus,
    AssignmentSubmissionRequest,
    ExtractionMethod,
    ExtractionStatus,
    FlashcardSetGenerationRequest,
    KoreanLevel,
    QuestionType,
)
from shiloh.services.ai import AIService, build_openai_json_schema


class FakeResponsesAPI:
    def __init__(self, output_text: str, *, validate_schema: bool = False) -> None:
        self.output_text = output_text
        self.validate_schema = validate_schema
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        if self.validate_schema:
            schema = kwargs["text"]["format"]["schema"]
            invalid_path = find_invalid_openai_object_schema(schema)
            if invalid_path:
                raise RuntimeError(
                    "Error code: 400 - {'error': {'message': "
                    f"\"Invalid schema for response_format 'assignment_generation': "
                    f"In context={invalid_path}, 'additionalProperties' is required to be supplied "
                    "and to be false.\", 'type': 'invalid_request_error', "
                    "'param': 'text.format.schema', 'code': 'invalid_json_schema'}}"
                )
        self.calls.append(kwargs)
        return type("FakeOpenAIResponse", (), {"output_text": self.output_text})()


class FakeOpenAIClient:
    def __init__(self, output_text: str, *, validate_schema: bool = False) -> None:
        self.responses = FakeResponsesAPI(
            output_text,
            validate_schema=validate_schema,
        )


def find_invalid_openai_object_schema(
    node: Any,
    *,
    path: tuple[str, ...] = (),
) -> tuple[str, ...] | None:
    if isinstance(node, dict):
        if node.get("type") == "object":
            properties = node.get("properties", {})
            if node.get("additionalProperties") is not False:
                return path
            if isinstance(properties, dict):
                required = node.get("required", [])
                if list(required) != list(properties.keys()):
                    return (*path, "required")
        for key, value in node.items():
            nested = find_invalid_openai_object_schema(value, path=(*path, key))
            if nested is not None:
                return nested
    elif isinstance(node, list):
        for index, value in enumerate(node):
            nested = find_invalid_openai_object_schema(
                value,
                path=(*path, str(index)),
            )
            if nested is not None:
                return nested
    return None


def make_settings(*, api_key: str | None) -> Settings:
    return Settings(
        jwt_secret="test-secret-with-at-least-thirty-two-bytes",
        internal_auth_secret="internal-secret-with-at-least-thirty-two-bytes",
        openai_api_key=api_key,
    )


def sample_generate_request() -> AssignmentGenerateTextRequest:
    return AssignmentGenerateTextRequest(
        title="Greetings",
        target_level=KoreanLevel.beginner,
        source_text="안녕하세요. 만나서 반갑습니다.",
        study_context="Keep the wording simple.",
    )


def sample_assignment_response() -> AssignmentResponse:
    question = AssignmentQuestionResponse(
        id="question-1",
        type=QuestionType.short_answer,
        prompt="Translate hello to Korean.",
        options=[],
        correct_answer="안녕하세요",
        accepted_answers=["안녕하세요", "안녕"],
    )
    return AssignmentResponse(
        id="assignment-1",
        owner_id="user-1",
        source=AssignmentSource.manual,
        title="Greetings",
        instructions="Keep the wording simple.",
        target_level=KoreanLevel.beginner,
        status=AssignmentStatus.ready,
        source_text="안녕하세요. 만나서 반갑습니다.",
        source_file=None,
        source_extraction_status=ExtractionStatus.ready,
        source_extraction_method=ExtractionMethod.text,
        source_markdown="안녕하세요. 만나서 반갑습니다.",
        source_extraction_summary={"character_count": 16},
        generation_error=None,
        generation_failed_at=None,
        generation_failures=[],
        questions=[question],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        latest_attempt=None,
        attempts=[],
    )


def sample_flashcard_request() -> FlashcardSetGenerationRequest:
    return FlashcardSetGenerationRequest(
        name="Travel Words",
        description="Common travel vocabulary.",
        source_text="공항 - airport\n호텔 - hotel",
        flashcards=[
            {"korean": "공항", "english": "airport"},
            {"korean": "호텔", "english": "hotel"},
        ],
    )


@pytest.mark.asyncio
async def test_generate_assignment_uses_openai_with_expected_prompt_and_schema() -> (
    None
):
    output_text = json.dumps(
        {
            "instructions": "Use the source text to answer.",
            "questions": [
                {
                    "id": "question-1",
                    "type": "multiple_choice",
                    "prompt": "Choose the greeting.",
                    "options": ["안녕하세요", "학교"],
                    "correct_answer": "안녕하세요",
                    "accepted_answers": ["안녕하세요"],
                    "explanation": "The greeting is explicit in the source.",
                }
            ],
        },
        ensure_ascii=False,
    )
    service = AIService(make_settings(api_key="test-key"))
    client = FakeOpenAIClient(output_text, validate_schema=True)
    service.client = client

    payload = await service.generate_assignment(sample_generate_request())

    assert payload.instructions == "Use the source text to answer."
    assert payload.questions[0].correct_answer == "안녕하세요"
    call = client.responses.calls[0]
    assert call["model"] == "gpt-5-mini"
    assert "Target Korean level: beginner." in call["input"]
    assert "Assignment title: Greetings" in call["input"]
    assert "안녕하세요. 만나서 반갑습니다." in call["input"]
    assert "Keep the wording simple." in call["input"]
    assert "assignment extraction service" in call["input"]
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True


@pytest.mark.asyncio
async def test_generate_flashcard_set_uses_openai_with_expected_prompt_and_schema() -> (
    None
):
    output_text = json.dumps(
        {
            "description": "Travel vocabulary for beginner review.",
            "tags": ["travel", "nouns"],
            "flashcards": [
                {
                    "korean": "공항",
                    "english": "airport",
                    "difficulty": "hard",
                    "tags": ["travel"],
                    "starred": False,
                    "notes": "Useful in airport travel questions.",
                    "example": "공항에서 비행기를 기다려요.",
                },
                {
                    "korean": "호텔",
                    "english": "hotel",
                    "difficulty": "medium",
                    "tags": ["travel"],
                    "starred": False,
                    "notes": "A common lodging word.",
                    "example": "호텔에서 하루 묵어요.",
                },
            ],
        },
        ensure_ascii=False,
    )
    service = AIService(make_settings(api_key="test-key"))
    client = FakeOpenAIClient(output_text, validate_schema=True)
    service.client = client

    payload = await service.generate_flashcard_set(sample_flashcard_request())

    assert payload.description == "Travel vocabulary for beginner review."
    assert payload.flashcards[0].korean == "공항"
    call = client.responses.calls[0]
    assert call["model"] == "gpt-5-mini"
    assert "Do not add cards, remove cards, merge cards, reorder cards" in call["input"]
    assert "Set name: Travel Words" in call["input"]
    assert '"korean": "공항"' in call["input"]
    assert call["text"]["format"]["name"] == "flashcard_set_generation"


@pytest.mark.asyncio
async def test_grade_assignment_uses_openai_with_expected_prompt_and_schema() -> None:
    output_text = json.dumps(
        {
            "overall_feedback": "Good job.",
            "graded_answers": [
                {
                    "question_id": "question-1",
                    "expected_answer": "안녕하세요",
                    "is_correct": True,
                    "score": 1,
                    "feedback": "Accepted.",
                }
            ],
        },
        ensure_ascii=False,
    )
    service = AIService(make_settings(api_key="test-key"))
    client = FakeOpenAIClient(output_text, validate_schema=True)
    service.client = client

    payload = await service.grade_assignment(
        sample_assignment_response(),
        AssignmentSubmissionRequest(
            answers=[{"question_id": "question-1", "answer": "안녕하세요"}]
        ),
    )

    assert payload.graded_answers[0].is_correct is True
    call = client.responses.calls[0]
    assert "Target Korean level: beginner." in call["input"]
    assert '"prompt": "Translate hello to Korean."' in call["input"]
    assert '"question-1": "안녕하세요"' in call["input"]
    assert call["text"]["format"]["name"] == "assignment_grading"


@pytest.mark.asyncio
async def test_generate_assignment_raises_predictable_error_for_malformed_output() -> (
    None
):
    service = AIService(make_settings(api_key="test-key"))
    service.client = FakeOpenAIClient("{not-json")

    with pytest.raises(json.JSONDecodeError):
        await service.generate_assignment(sample_generate_request())


@pytest.mark.asyncio
async def test_generate_flashcard_set_rejects_ai_that_rewrites_pairs() -> None:
    service = AIService(make_settings(api_key="test-key"))
    service.client = FakeOpenAIClient(
        json.dumps(
            {
                "description": "Modified output.",
                "tags": ["travel"],
                "flashcards": [
                    {
                        "korean": "공항",
                        "english": "airport terminal",
                        "difficulty": "medium",
                        "tags": ["travel"],
                        "starred": False,
                        "notes": "Changed definition.",
                        "example": "공항에서 기다려요.",
                    },
                    {
                        "korean": "호텔",
                        "english": "hotel",
                        "difficulty": "medium",
                        "tags": ["travel"],
                        "starred": False,
                        "notes": "Lodging term.",
                        "example": "호텔에 도착했어요.",
                    },
                ],
            },
            ensure_ascii=False,
        )
    )

    with pytest.raises(RuntimeError, match="English definition for flashcard 1"):
        await service.generate_flashcard_set(sample_flashcard_request())


@pytest.mark.asyncio
async def test_grade_assignment_raises_predictable_error_for_invalid_schema() -> None:
    invalid_output = json.dumps({"overall_feedback": "Missing graded answers."})
    service = AIService(make_settings(api_key="test-key"))
    service.client = FakeOpenAIClient(invalid_output)

    with pytest.raises(ValidationError):
        await service.grade_assignment(
            sample_assignment_response(),
            AssignmentSubmissionRequest(
                answers=[{"question_id": "question-1", "answer": "안녕하세요"}]
            ),
        )


def test_build_openai_json_schema_marks_objects_as_strict_and_requires_all_properties() -> (
    None
):
    schema = build_openai_json_schema(AssignmentGenerationPayload)

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["instructions", "questions"]
    question_schema = schema["$defs"]["AssignmentQuestionInput"]
    assert question_schema["additionalProperties"] is False
    assert question_schema["required"] == [
        "id",
        "type",
        "prompt",
        "options",
        "correct_answer",
        "accepted_answers",
        "explanation",
    ]
    assert "default" not in question_schema["properties"]["id"]
    assert "default" not in question_schema["properties"]["explanation"]


@pytest.mark.asyncio
async def test_fallback_generation_and_grading_work_without_openai_key() -> None:
    service = AIService(make_settings(api_key=None))

    generated = await service.generate_assignment(sample_generate_request())
    assert generated.instructions
    assert len(generated.questions) >= 3

    generated_flashcards = await service.generate_flashcard_set(
        sample_flashcard_request()
    )
    assert generated_flashcards.description
    assert len(generated_flashcards.flashcards) == 2
    assert generated_flashcards.flashcards[0].korean == "공항"
    assert generated_flashcards.flashcards[0].difficulty == "medium"

    graded = await service.grade_assignment(
        sample_assignment_response(),
        AssignmentSubmissionRequest(
            answers=[{"question_id": "question-1", "answer": "안녕하세요"}]
        ),
    )
    assert graded.graded_answers[0].is_correct is True


LIVE_OPENAI_ENABLED = bool(
    os.getenv("OPENAI_LIVE_TEST") == "1" and os.getenv("OPENAI_API_KEY")
)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not LIVE_OPENAI_ENABLED,
    reason="Set OPENAI_LIVE_TEST=1 and OPENAI_API_KEY to run live OpenAI smoke tests.",
)
async def test_live_openai_generation_returns_schema_valid_assignment() -> None:
    service = AIService(make_settings(api_key=os.environ["OPENAI_API_KEY"]))

    generated = await service.generate_assignment(sample_generate_request())

    assert generated.instructions.strip()
    assert 1 <= len(generated.questions)
    assert all(question.prompt.strip() for question in generated.questions)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not LIVE_OPENAI_ENABLED,
    reason="Set OPENAI_LIVE_TEST=1 and OPENAI_API_KEY to run live OpenAI smoke tests.",
)
async def test_live_openai_grading_returns_schema_valid_feedback() -> None:
    service = AIService(make_settings(api_key=os.environ["OPENAI_API_KEY"]))

    graded = await service.grade_assignment(
        sample_assignment_response(),
        AssignmentSubmissionRequest(
            answers=[{"question_id": "question-1", "answer": "안녕하세요"}]
        ),
    )

    assert graded.overall_feedback.strip()
    assert len(graded.graded_answers) == 1
    assert graded.graded_answers[0].feedback.strip()
