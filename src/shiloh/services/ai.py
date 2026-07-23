from __future__ import annotations

import json
import re
from random import shuffle
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI
from pydantic import BaseModel

from shiloh.config import Settings
from shiloh.schemas import (
    AssignmentGenerateTextRequest,
    AssignmentGenerationPayload,
    AssignmentGradeDecision,
    AssignmentGradePayload,
    AssignmentQuestionInput,
    AssignmentSubmissionRequest,
    AssignmentResponse,
    FlashcardCreate,
    FlashcardSetGenerationPayload,
    FlashcardSetGenerationRequest,
    QuestionType,
)


def _normalize_openai_schema(node: Any) -> Any:
    if isinstance(node, dict):
        normalized = {}
        for key, value in node.items():
            if key == "default":
                continue
            normalized[key] = _normalize_openai_schema(value)
        if normalized.get("type") == "object":
            properties = normalized.get("properties", {})
            if isinstance(properties, dict):
                normalized["required"] = list(properties.keys())
            normalized["additionalProperties"] = False
        return normalized
    if isinstance(node, list):
        return [_normalize_openai_schema(item) for item in node]
    return node


def build_openai_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return _normalize_openai_schema(model.model_json_schema())


class AIService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = (
            AsyncOpenAI(api_key=settings.openai_api_key)
            if settings.openai_api_key
            else None
        )

    async def generate_assignment(
        self,
        request: AssignmentGenerateTextRequest,
    ) -> AssignmentGenerationPayload:
        if self.client is None:
            return self._generate_fallback_assignment(request)

        schema = build_openai_json_schema(AssignmentGenerationPayload)
        prompt = (
            "You are an assignment extraction service for Korean language learners.\n"
            f"Target Korean level: {request.target_level}.\n"
            "Extract the full assignment details from the supplied material. Create concise learner-facing instructions and "
            "generate 4 to 6 questions using only these types: multiple_choice, fill_blank, short_answer.\n"
            "Each question must include a canonical correct_answer, accepted_answers, and an explanation.\n"
            "Keep prompts and expected answers appropriate for the requested learner level and grounded in the source material.\n"
            f"Assignment title: {request.title}\n"
            f"Source material:\n{request.source_text}\n"
            f"Supplemental study context (optional):\n{request.study_context or 'None provided.'}"
        )
        response = await self.client.responses.create(
            model=self.settings.openai_model,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "assignment_generation",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        payload = json.loads(response.output_text)
        return AssignmentGenerationPayload.model_validate(payload)

    async def generate_flashcard_set(
        self,
        request: FlashcardSetGenerationRequest,
    ) -> FlashcardSetGenerationPayload:
        if self.client is None:
            return self._generate_fallback_flashcard_set(request)

        schema = build_openai_json_schema(FlashcardSetGenerationPayload)
        prompt = (
            "You are enriching a Korean language-learning flashcard set.\n"
            "Do not add cards, remove cards, merge cards, reorder cards, or rewrite the submitted Korean-English pairs.\n"
            "You may only enrich each card with difficulty, tags, notes, and a concise Korean example sentence.\n"
            "Set starred to false for every generated card; learners manage stars themselves.\n"
            "Return the cards in the exact same order they were submitted.\n"
            f"Set name: {request.name}\n"
            f"Existing description: {request.description or 'None provided.'}\n"
            f"Submitted pairs:\n{json.dumps([card.model_dump() for card in request.flashcards], ensure_ascii=False)}"
        )
        response = await self.client.responses.create(
            model=self.settings.openai_model,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "flashcard_set_generation",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        payload = FlashcardSetGenerationPayload.model_validate(
            json.loads(response.output_text)
        )
        self._validate_generated_flashcards(request, payload)
        return payload

    async def grade_assignment(
        self,
        assignment: AssignmentResponse,
        submission: AssignmentSubmissionRequest,
    ) -> AssignmentGradePayload:
        if self.client is None:
            return self._grade_fallback_assignment(assignment, submission)

        schema = build_openai_json_schema(AssignmentGradePayload)
        answers = {answer.question_id: answer.answer for answer in submission.answers}
        prompt = (
            "You are grading a Korean language-learning assignment.\n"
            f"Target Korean level: {assignment.target_level}.\n"
            "For each question, decide whether the learner answer is correct for that level, provide concise feedback, "
            "and include the expected_answer you used.\n"
            "Be flexible with equivalent answers and natural phrasing when they fit the level.\n"
            f"Assignment questions:\n{json.dumps([question.model_dump() for question in assignment.questions], ensure_ascii=False)}\n"
            f"Learner answers:\n{json.dumps(answers, ensure_ascii=False)}"
        )
        response = await self.client.responses.create(
            model=self.settings.openai_model,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "assignment_grading",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        payload = json.loads(response.output_text)
        return AssignmentGradePayload.model_validate(payload)

    def _generate_fallback_assignment(
        self,
        request: AssignmentGenerateTextRequest,
    ) -> AssignmentGenerationPayload:
        tokens = re.findall(r"[가-힣]+", request.source_text or "")
        seed_words = tokens[:3] or ["안녕하세요", "사과", "학교"]
        options = seed_words + ["감사합니다", "친구"]
        shuffle(options)
        questions = [
            AssignmentQuestionInput(
                id=str(uuid4()),
                type=QuestionType.multiple_choice,
                prompt=f"Which option appears in the source material for '{request.title}'?",
                options=options,
                correct_answer=seed_words[0],
                accepted_answers=[seed_words[0]],
                explanation="Choose the word that appeared in the source text.",
            ),
            AssignmentQuestionInput(
                id=str(uuid4()),
                type=QuestionType.fill_blank,
                prompt=f"Fill in the blank with a Korean word from the source: ______ ({request.target_level})",
                correct_answer=seed_words[min(1, len(seed_words) - 1)],
                accepted_answers=[seed_words[min(1, len(seed_words) - 1)]],
                explanation="Use a Korean word from the submitted material.",
            ),
            AssignmentQuestionInput(
                id=str(uuid4()),
                type=QuestionType.short_answer,
                prompt="Write one short Korean sentence that uses one of the source words correctly.",
                correct_answer=f"{seed_words[0]}를 사용한 짧은 문장",
                accepted_answers=[f"{seed_words[0]}를 사용한 짧은 문장", seed_words[0]],
                explanation="Any short sentence that uses the source word appropriately can be accepted.",
            ),
        ]
        return AssignmentGenerationPayload(
            instructions="Answer each question using the Korean source material.",
            questions=questions,
        )

    def _grade_fallback_assignment(
        self,
        assignment: AssignmentResponse,
        submission: AssignmentSubmissionRequest,
    ) -> AssignmentGradePayload:
        answer_map = {
            answer.question_id: answer.answer for answer in submission.answers
        }
        graded_answers: list[AssignmentGradeDecision] = []
        correct_total = 0.0
        for question in assignment.questions:
            user_answer = answer_map.get(question.id, "")
            expected_answers = {
                item.strip().lower() for item in question.accepted_answers
            }
            normalized = user_answer.strip().lower()
            is_correct = normalized in expected_answers
            if question.type == QuestionType.short_answer and not is_correct:
                is_correct = any(
                    candidate in normalized
                    for candidate in expected_answers
                    if candidate
                )
            score = 1.0 if is_correct else 0.0
            correct_total += score
            graded_answers.append(
                AssignmentGradeDecision(
                    question_id=question.id,
                    expected_answer=question.correct_answer,
                    is_correct=is_correct,
                    score=score,
                    feedback="Accepted."
                    if is_correct
                    else "Review the target expression and try again.",
                )
            )
        overall = correct_total / max(len(assignment.questions), 1)
        return AssignmentGradePayload(
            overall_feedback="Strong work."
            if overall >= 0.75
            else "Review the corrections and retry the assignment.",
            graded_answers=graded_answers,
        )

    def _generate_fallback_flashcard_set(
        self,
        request: FlashcardSetGenerationRequest,
    ) -> FlashcardSetGenerationPayload:
        flashcards = [
            FlashcardCreate(
                korean=card.korean,
                english=card.english,
                difficulty="medium",
                tags=[],
                notes=f"Study the meaning and usage of '{card.english}'.",
                example=f'"{card.korean}"를 문장에서 연습해 보세요.',
            )
            for card in request.flashcards
        ]
        payload = FlashcardSetGenerationPayload(
            description=request.description
            or f"AI-enriched flashcard set for {request.name}.",
            tags=[],
            flashcards=flashcards,
        )
        self._validate_generated_flashcards(request, payload)
        return payload

    def _validate_generated_flashcards(
        self,
        request: FlashcardSetGenerationRequest,
        payload: FlashcardSetGenerationPayload,
    ) -> None:
        if len(payload.flashcards) != len(request.flashcards):
            raise RuntimeError(
                "AI returned a different number of flashcards than were submitted."
            )
        for index, (submitted, generated) in enumerate(
            zip(request.flashcards, payload.flashcards, strict=True),
            start=1,
        ):
            if submitted.korean.strip() != generated.korean.strip():
                raise RuntimeError(f"AI changed the Korean term for flashcard {index}.")
            if submitted.english.strip() != generated.english.strip():
                raise RuntimeError(
                    f"AI changed the English definition for flashcard {index}."
                )
