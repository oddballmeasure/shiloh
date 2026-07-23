from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shiloh.utils import dedupe_strings


class UserRole(str, Enum):
    learner = "learner"
    admin = "admin"
    super_admin = "super_admin"


class UserStatus(str, Enum):
    active = "active"
    deactivated = "deactivated"


class FlashcardDifficulty(str, Enum):
    hard = "hard"
    medium = "medium"
    easy = "easy"


class FlashcardSetStatus(str, Enum):
    processing = "processing"
    failed = "failed"
    active = "active"
    done = "done"


class FlashcardSetSource(str, Enum):
    manual = "manual"
    ai_list = "ai_list"


class AssignmentSource(str, Enum):
    manual = "manual"
    ai_text = "ai_text"
    ai_pdf = "ai_pdf"


class AssignmentStatus(str, Enum):
    processing = "processing"
    ready = "ready"
    failed = "failed"
    completed = "completed"


class KoreanLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class QuestionType(str, Enum):
    multiple_choice = "multiple_choice"
    fill_blank = "fill_blank"
    short_answer = "short_answer"


class APIModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True)


class UserResponse(APIModel):
    id: str
    discord_id: str
    email: str | None = None
    username: str
    avatar_url: str | None = None
    discord_profile_snapshot: dict[str, Any] | None = None
    last_login_at: datetime | None = None
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class DiscordSyncRequest(APIModel):
    discord_id: str
    email: str | None = None
    username: str
    avatar_url: str | None = None
    discord_profile_snapshot: dict[str, Any] | None = None


class AuthSyncResponse(APIModel):
    access_token: str
    user: UserResponse


class ProfileSummary(APIModel):
    user: UserResponse
    words_learned: int
    assignments_completed: int
    flashcard_count: int
    flashcard_set_count: int
    done_set_count: int
    assignments_generated: int
    assignments_manual: int


class FlashcardSetCreate(APIModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_tags(self) -> "FlashcardSetCreate":
        self.tags = dedupe_strings(self.tags)
        return self


class FlashcardSetGenerateRequest(APIModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    source_text: str = Field(min_length=1, max_length=12000)


class FlashcardSetUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    tags: list[str] | None = None

    @model_validator(mode="after")
    def normalize_tags(self) -> "FlashcardSetUpdate":
        if self.tags is not None:
            self.tags = dedupe_strings(self.tags)
        return self


class FlashcardSetResponse(APIModel):
    id: str
    owner_id: str
    source: FlashcardSetSource = FlashcardSetSource.manual
    name: str
    description: str | None = None
    tags: list[str]
    status: FlashcardSetStatus
    source_text: str | None = None
    generation_error: str | None = None
    generation_failed_at: datetime | None = None
    generation_failures: list["FlashcardGenerationFailure"] = Field(
        default_factory=list
    )
    created_at: datetime
    updated_at: datetime


class FlashcardCreate(APIModel):
    korean: str = Field(min_length=1, max_length=120)
    english: str = Field(min_length=1, max_length=240)
    notes: str | None = Field(default=None, max_length=500)
    example: str | None = Field(default=None, max_length=500)
    difficulty: FlashcardDifficulty = FlashcardDifficulty.medium
    tags: list[str] = Field(default_factory=list)
    starred: bool = False

    @model_validator(mode="after")
    def normalize_tags(self) -> "FlashcardCreate":
        self.tags = dedupe_strings(self.tags)
        return self


class FlashcardUpdate(APIModel):
    korean: str | None = Field(default=None, min_length=1, max_length=120)
    english: str | None = Field(default=None, min_length=1, max_length=240)
    notes: str | None = Field(default=None, max_length=500)
    example: str | None = Field(default=None, max_length=500)
    difficulty: FlashcardDifficulty | None = None
    tags: list[str] | None = None
    starred: bool | None = None

    @model_validator(mode="after")
    def normalize_tags(self) -> "FlashcardUpdate":
        if self.tags is not None:
            self.tags = dedupe_strings(self.tags)
        return self


class FlashcardSeedInput(APIModel):
    korean: str = Field(min_length=1, max_length=120)
    english: str = Field(min_length=1, max_length=240)


class FlashcardSetGenerationRequest(APIModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    source_text: str = Field(min_length=1, max_length=12000)
    flashcards: list[FlashcardSeedInput] = Field(min_length=1, max_length=500)


class FlashcardGenerationFailure(APIModel):
    stage: Literal["generation"]
    message: str
    occurred_at: datetime


class FlashcardReviewRequest(APIModel):
    difficulty: FlashcardDifficulty


class FlashcardResponse(APIModel):
    id: str
    owner_id: str
    set_id: str
    korean: str
    english: str
    notes: str | None = None
    example: str | None = None
    difficulty: FlashcardDifficulty
    tags: list[str]
    starred: bool = False
    correct_reviews: int
    incorrect_reviews: int
    last_reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class FlashcardSetGenerationPayload(APIModel):
    description: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list)
    flashcards: list[FlashcardCreate] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def normalize_tags(self) -> "FlashcardSetGenerationPayload":
        self.tags = dedupe_strings(self.tags)
        return self


class StudySessionRequest(APIModel):
    limit: int = Field(default=20, ge=1, le=200)


class StudySessionResponse(APIModel):
    flashcards: list[FlashcardResponse]
    set_status: FlashcardSetStatus


class AssignmentQuestionInput(APIModel):
    id: str | None = None
    type: QuestionType
    prompt: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(default_factory=list, max_length=8)
    correct_answer: str = Field(min_length=1, max_length=240)
    accepted_answers: list[str] = Field(default_factory=list)
    explanation: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def normalize_options(self) -> "AssignmentQuestionInput":
        self.options = dedupe_strings(self.options)
        self.accepted_answers = dedupe_strings(
            [self.correct_answer, *self.accepted_answers]
        )
        return self

    @model_validator(mode="after")
    def validate_shape(self) -> "AssignmentQuestionInput":
        if self.type == QuestionType.multiple_choice and len(self.options) < 2:
            raise ValueError("Multiple-choice questions require at least two options.")
        if self.type != QuestionType.multiple_choice and self.options:
            raise ValueError("Only multiple-choice questions may include options.")
        return self


class AssignmentCreateRequest(APIModel):
    title: str = Field(min_length=1, max_length=120)
    instructions: str | None = Field(default=None, max_length=1000)
    target_level: KoreanLevel
    questions: list[AssignmentQuestionInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_shape(self) -> "AssignmentCreateRequest":
        if not self.questions:
            raise ValueError("Manual assignments require at least one question.")
        return self


class AssignmentGenerateTextRequest(APIModel):
    title: str = Field(min_length=1, max_length=120)
    target_level: KoreanLevel
    source_text: str = Field(min_length=1, max_length=12000)
    study_context: str | None = Field(default=None, max_length=1000)


class AssignmentSourceFile(APIModel):
    id: str
    filename: str
    size_bytes: int
    content_type: str
    sha256: str


class ExtractionStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class ExtractionMethod(str, Enum):
    text = "text"
    pymupdf4llm = "pymupdf4llm"
    ocrmypdf_pymupdf4llm = "ocrmypdf+pymupdf4llm"


class AssignmentUpdateRequest(APIModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    instructions: str | None = Field(default=None, max_length=1000)
    target_level: KoreanLevel | None = None
    questions: list[AssignmentQuestionInput] | None = None


class AssignmentQuestionResponse(APIModel):
    id: str
    type: QuestionType
    prompt: str
    options: list[str]
    correct_answer: str
    accepted_answers: list[str]
    explanation: str | None = None


class AnswerSubmission(APIModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=1000)


class AssignmentSubmissionRequest(APIModel):
    answers: list[AnswerSubmission]


class GradedAnswerResponse(APIModel):
    question_id: str
    answer: str
    expected_answer: str
    is_correct: bool
    score: float
    feedback: str


class AssignmentAttemptResponse(APIModel):
    id: str
    assignment_id: str
    owner_id: str
    answers: list[AnswerSubmission]
    graded_answers: list[GradedAnswerResponse]
    score: float
    feedback: str
    completed_at: datetime
    created_at: datetime


class AssignmentGenerationFailure(APIModel):
    stage: Literal["extraction", "generation"]
    message: str
    occurred_at: datetime


class AssignmentResponse(APIModel):
    id: str
    owner_id: str
    source: AssignmentSource
    title: str
    instructions: str | None = None
    target_level: KoreanLevel
    status: AssignmentStatus
    source_text: str | None = None
    source_file: AssignmentSourceFile | None = None
    source_extraction_status: ExtractionStatus
    source_extraction_method: ExtractionMethod | None = None
    source_markdown: str | None = None
    source_extraction_summary: dict[str, Any] | None = None
    generation_error: str | None = None
    generation_failed_at: datetime | None = None
    generation_failures: list[AssignmentGenerationFailure] = Field(default_factory=list)
    completed_at: datetime | None = None
    questions: list[AssignmentQuestionResponse]
    created_at: datetime
    updated_at: datetime
    latest_attempt: AssignmentAttemptResponse | None = None
    attempts: list[AssignmentAttemptResponse] = Field(default_factory=list)


class AdminUserListItem(APIModel):
    id: str
    discord_id: str
    email: str | None = None
    username: str
    avatar_url: str | None = None
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class AdminUserDetail(APIModel):
    user: UserResponse
    flashcard_sets: list[FlashcardSetResponse]
    flashcards: list[FlashcardResponse]
    assignments: list[AssignmentResponse]


class AssignmentGenerationPayload(APIModel):
    instructions: str
    questions: list[AssignmentQuestionInput]


class AssignmentGradeDecision(APIModel):
    question_id: str
    expected_answer: str
    is_correct: bool
    score: float = Field(ge=0, le=1)
    feedback: str


class AssignmentGradePayload(APIModel):
    overall_feedback: str
    graded_answers: list[AssignmentGradeDecision]
