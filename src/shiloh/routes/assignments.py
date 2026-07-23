from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)

from shiloh.config import Settings
from shiloh.dependencies import (
    get_app_settings,
    get_current_user,
    get_database,
    get_file_storage,
)
from shiloh.schemas import (
    AssignmentAttemptResponse,
    AssignmentCreateRequest,
    AssignmentGenerationFailure,
    AssignmentGenerateTextRequest,
    AssignmentQuestionResponse,
    AssignmentResponse,
    AssignmentSource,
    AssignmentSourceFile,
    AssignmentStatus,
    AssignmentSubmissionRequest,
    AssignmentUpdateRequest,
    ExtractionMethod,
    ExtractionStatus,
    GradedAnswerResponse,
    KoreanLevel,
)
from shiloh.utils import serialize_document, to_object_id, utcnow

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


async def _latest_attempt(
    db, assignment_id: str, owner_id: str
) -> AssignmentAttemptResponse | None:
    attempts = await _assignment_attempts(db, assignment_id, owner_id)
    return attempts[0] if attempts else None


async def _assignment_attempts(
    db, assignment_id: str, owner_id: str
) -> list[AssignmentAttemptResponse]:
    cursor = db.assignment_attempts.find(
        {"assignment_id": assignment_id, "owner_id": owner_id}
    ).sort("completed_at", -1)
    documents = await cursor.to_list(length=500)
    return [
        AssignmentAttemptResponse.model_validate(serialize_document(document))
        for document in documents
    ]


async def _get_owned_assignment(db, owner_id: str, assignment_id: str) -> dict:
    document = await db.assignments.find_one(
        {"_id": to_object_id(assignment_id), "owner_id": owner_id}
    )
    serialized = serialize_document(document)
    if serialized is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found."
        )
    return serialized


def _assignment_response(
    document: dict,
    latest_attempt: AssignmentAttemptResponse | None,
    attempts: list[AssignmentAttemptResponse] | None = None,
) -> AssignmentResponse:
    payload = dict(document)
    payload["latest_attempt"] = latest_attempt
    payload["attempts"] = attempts or []
    payload["questions"] = [
        AssignmentQuestionResponse.model_validate(question)
        for question in payload.get("questions", [])
    ]
    return AssignmentResponse.model_validate(payload)


def _assignment_file(document: dict) -> AssignmentSourceFile | None:
    source_file = document.get("source_file")
    if not source_file:
        return None
    return AssignmentSourceFile.model_validate(source_file)


async def _delete_assignment_resources(db, file_storage, assignment: dict) -> None:
    source_file = _assignment_file(assignment)
    if source_file is not None:
        try:
            await file_storage.delete(source_file.id)
        except Exception as exc:  # pragma: no cover - defensive runtime path
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to delete the assignment file right now. Please try again.",
            ) from exc
    await db.assignment_attempts.delete_many({"assignment_id": assignment["id"]})
    await db.assignments.delete_one({"_id": to_object_id(assignment["id"])})


async def _record_generation_failure(
    db,
    assignment_id: str,
    *,
    stage: str,
    message: str,
    source_extraction_status: str,
) -> None:
    existing = serialize_document(
        await db.assignments.find_one({"_id": to_object_id(assignment_id)})
    )
    if existing is None:
        return
    failed_at = utcnow()
    failures = [
        *existing.get("generation_failures", []),
        AssignmentGenerationFailure(
            stage=stage,
            message=message,
            occurred_at=failed_at,
        ).model_dump(),
    ]
    await db.assignments.update_one(
        {"_id": to_object_id(assignment_id)},
        {
            "$set": {
                "status": AssignmentStatus.failed.value,
                "source_extraction_status": source_extraction_status,
                "generation_error": message,
                "generation_failed_at": failed_at,
                "generation_failures": failures,
                "completed_at": None,
                "updated_at": failed_at,
            }
        },
    )


async def _process_generated_text_assignment(
    app,
    assignment_id: str,
    generation_request: AssignmentGenerateTextRequest,
) -> None:
    db = app.state.db
    now = utcnow()
    try:
        generated = await app.state.ai_service.generate_assignment(generation_request)
        await db.assignments.update_one(
            {"_id": to_object_id(assignment_id)},
            {
                "$set": {
                    "instructions": generated.instructions,
                    "questions": [
                        {
                            **question.model_dump(),
                            "id": question.id or str(uuid4()),
                        }
                        for question in generated.questions
                    ],
                    "status": AssignmentStatus.ready.value,
                    "source_extraction_status": ExtractionStatus.ready.value,
                    "source_extraction_method": ExtractionMethod.text.value,
                    "generation_error": None,
                    "generation_failed_at": None,
                    "generation_failures": [],
                    "completed_at": None,
                    "updated_at": now,
                }
            },
        )
    except Exception as exc:  # pragma: no cover - defensive runtime path
        await _record_generation_failure(
            db,
            assignment_id,
            stage="generation",
            message=str(exc),
            source_extraction_status=ExtractionStatus.ready.value,
        )


async def _process_generated_pdf_assignment(app, assignment_id: str) -> None:
    db = app.state.db
    assignment = serialize_document(
        await db.assignments.find_one({"_id": to_object_id(assignment_id)})
    )
    if assignment is None:
        return

    source_file = _assignment_file(assignment)
    if source_file is None:
        await _record_generation_failure(
            db,
            assignment_id,
            stage="extraction",
            message="Source PDF not found for processing.",
            source_extraction_status=ExtractionStatus.failed.value,
        )
        return

    try:
        file_bytes = await app.state.file_storage.download_bytes(source_file.id)
        extracted = await app.state.pdf_service.extract(
            file_bytes=file_bytes,
            filename=source_file.filename,
        )
        generation_request = AssignmentGenerateTextRequest(
            title=assignment["title"],
            target_level=assignment["target_level"],
            source_text=extracted.markdown,
            study_context=assignment.get("source_text"),
        )
    except Exception as exc:  # pragma: no cover - defensive runtime path
        await _record_generation_failure(
            db,
            assignment_id,
            stage="extraction",
            message=str(exc),
            source_extraction_status=ExtractionStatus.failed.value,
        )
        return

    try:
        generated = await app.state.ai_service.generate_assignment(generation_request)
        await db.assignments.update_one(
            {"_id": to_object_id(assignment_id)},
            {
                "$set": {
                    "instructions": generated.instructions,
                    "questions": [
                        {
                            **question.model_dump(),
                            "id": question.id or str(uuid4()),
                        }
                        for question in generated.questions
                    ],
                    "status": AssignmentStatus.ready.value,
                    "source_extraction_status": ExtractionStatus.ready.value,
                    "source_extraction_method": extracted.method,
                    "source_markdown": extracted.markdown,
                    "source_extraction_summary": extracted.summary,
                    "generation_error": None,
                    "generation_failed_at": None,
                    "generation_failures": [],
                    "completed_at": None,
                    "updated_at": utcnow(),
                }
            },
        )
    except Exception as exc:  # pragma: no cover - defensive runtime path
        await _record_generation_failure(
            db,
            assignment_id,
            stage="generation",
            message=str(exc),
            source_extraction_status=ExtractionStatus.ready.value,
        )


def _validate_pdf_upload(
    upload: UploadFile, file_bytes: bytes, settings: Settings
) -> None:
    if len(file_bytes) > settings.assignment_pdf_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="PDF exceeds the 50 MB upload limit.",
        )
    content_type = upload.content_type or ""
    filename = upload.filename or "assignment.pdf"
    if content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF uploads are supported.",
        )


@router.get("", response_model=list[AssignmentResponse])
async def list_assignments(
    user=Depends(get_current_user), db=Depends(get_database)
) -> list[AssignmentResponse]:
    cursor = db.assignments.find({"owner_id": user["id"]}).sort("updated_at", -1)
    documents = [serialize_document(item) for item in await cursor.to_list(length=500)]
    responses: list[AssignmentResponse] = []
    for document in documents:
        attempts = await _assignment_attempts(db, document["id"], user["id"])
        responses.append(
            _assignment_response(document, attempts[0] if attempts else None, attempts)
        )
    return responses


@router.post("", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_assignment(
    payload: AssignmentCreateRequest,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> AssignmentResponse:
    now = utcnow()
    questions = [
        {
            **question.model_dump(),
            "id": question.id or str(uuid4()),
        }
        for question in payload.questions
    ]
    document = {
        "owner_id": user["id"],
        "source": AssignmentSource.manual.value,
        "title": payload.title,
        "instructions": payload.instructions,
        "target_level": str(payload.target_level),
        "status": AssignmentStatus.ready.value,
        "source_text": None,
        "source_file": None,
        "source_extraction_status": ExtractionStatus.ready.value,
        "source_extraction_method": None,
        "source_markdown": None,
        "source_extraction_summary": None,
        "generation_error": None,
        "generation_failed_at": None,
        "generation_failures": [],
        "completed_at": None,
        "questions": questions,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.assignments.insert_one(document)
    created = await db.assignments.find_one({"_id": result.inserted_id})
    serialized = serialize_document(created)
    return _assignment_response(serialized, None, [])


@router.post(
    "/generate", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED
)
async def generate_assignment_from_text(
    request: Request,
    payload: AssignmentGenerateTextRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> AssignmentResponse:
    now = utcnow()
    document = {
        "owner_id": user["id"],
        "source": AssignmentSource.ai_text.value,
        "title": payload.title,
        "instructions": None,
        "target_level": str(payload.target_level),
        "status": AssignmentStatus.processing.value,
        "source_text": payload.source_text,
        "source_file": None,
        "source_extraction_status": ExtractionStatus.processing.value,
        "source_extraction_method": ExtractionMethod.text.value,
        "source_markdown": payload.source_text,
        "source_extraction_summary": {
            "character_count": len(payload.source_text),
            "used_ocr_fallback": False,
        },
        "generation_error": None,
        "generation_failed_at": None,
        "generation_failures": [],
        "completed_at": None,
        "questions": [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.assignments.insert_one(document)
    created = await db.assignments.find_one({"_id": result.inserted_id})
    serialized = serialize_document(created)
    background_tasks.add_task(
        _process_generated_text_assignment,
        request.app,
        serialized["id"],
        payload,
    )
    return _assignment_response(serialized, None, [])


@router.post(
    "/generate-from-pdf",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_assignment_from_pdf(
    request: Request,
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    target_level: KoreanLevel = Form(...),
    study_context: str | None = Form(default=None),
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db=Depends(get_database),
    file_storage=Depends(get_file_storage),
    settings: Settings = Depends(get_app_settings),
) -> AssignmentResponse:
    file_bytes = await file.read()
    _validate_pdf_upload(file, file_bytes, settings)
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    try:
        stored_file = await file_storage.store_bytes(
            data=file_bytes,
            filename=file.filename or "assignment.pdf",
            content_type=file.content_type or "application/pdf",
            sha256=sha256,
            metadata={"owner_id": user["id"], "kind": "assignment_pdf"},
        )
    except Exception as exc:  # pragma: no cover - defensive runtime path
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to store the uploaded PDF right now. Please try again.",
        ) from exc
    now = utcnow()
    document = {
        "owner_id": user["id"],
        "source": AssignmentSource.ai_pdf.value,
        "title": title,
        "instructions": None,
        "target_level": target_level.value,
        "status": AssignmentStatus.processing.value,
        "source_text": study_context,
        "source_file": {
            "id": stored_file.id,
            "filename": stored_file.filename,
            "size_bytes": stored_file.size_bytes,
            "content_type": stored_file.content_type,
            "sha256": stored_file.sha256,
        },
        "source_extraction_status": ExtractionStatus.processing.value,
        "source_extraction_method": None,
        "source_markdown": None,
        "source_extraction_summary": None,
        "generation_error": None,
        "generation_failed_at": None,
        "generation_failures": [],
        "completed_at": None,
        "questions": [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.assignments.insert_one(document)
    created = await db.assignments.find_one({"_id": result.inserted_id})
    serialized = serialize_document(created)
    background_tasks.add_task(
        _process_generated_pdf_assignment,
        request.app,
        serialized["id"],
    )
    return _assignment_response(serialized, None, [])


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: str,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> AssignmentResponse:
    assignment = await _get_owned_assignment(db, user["id"], assignment_id)
    attempts = await _assignment_attempts(db, assignment["id"], user["id"])
    return _assignment_response(assignment, attempts[0] if attempts else None, attempts)


@router.get("/{assignment_id}/source-file")
async def get_assignment_source_file(
    assignment_id: str,
    user=Depends(get_current_user),
    db=Depends(get_database),
    file_storage=Depends(get_file_storage),
) -> Response:
    assignment = await _get_owned_assignment(db, user["id"], assignment_id)
    source_file = _assignment_file(assignment)
    if source_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source file not found."
        )
    try:
        file_bytes = await file_storage.download_bytes(source_file.id)
    except Exception as exc:  # pragma: no cover - defensive runtime path
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to retrieve the submitted source file right now.",
        ) from exc
    return Response(
        content=file_bytes,
        media_type=source_file.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{source_file.filename}"',
        },
    )


@router.patch("/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: str,
    payload: AssignmentUpdateRequest,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> AssignmentResponse:
    assignment = await _get_owned_assignment(db, user["id"], assignment_id)
    update_fields = payload.model_dump(exclude_none=True)
    if (
        assignment["source"] != AssignmentSource.manual.value
        and "questions" in update_fields
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only manual assignments can update questions.",
        )
    if "questions" in update_fields and not (payload.questions or []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Manual assignments require at least one question.",
        )
    if "questions" in update_fields:
        update_fields["questions"] = [
            {
                **question.model_dump(),
                "id": question.id or str(uuid4()),
            }
            for question in payload.questions or []
        ]
    if "target_level" in update_fields:
        update_fields["target_level"] = str(update_fields["target_level"])
    if update_fields:
        update_fields["updated_at"] = utcnow()
        await db.assignments.update_one(
            {"_id": to_object_id(assignment_id), "owner_id": user["id"]},
            {"$set": update_fields},
        )
    document = await db.assignments.find_one({"_id": to_object_id(assignment_id)})
    attempts = await _assignment_attempts(db, assignment_id, user["id"])
    return _assignment_response(
        serialize_document(document), attempts[0] if attempts else None, attempts
    )


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: str,
    user=Depends(get_current_user),
    db=Depends(get_database),
    file_storage=Depends(get_file_storage),
) -> None:
    assignment = await _get_owned_assignment(db, user["id"], assignment_id)
    await _delete_assignment_resources(db, file_storage, assignment)


@router.post("/{assignment_id}/redo", response_model=AssignmentResponse)
async def redo_assignment(
    assignment_id: str,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> AssignmentResponse:
    assignment = await _get_owned_assignment(db, user["id"], assignment_id)
    if assignment["status"] != AssignmentStatus.completed.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed assignments can be reopened.",
        )
    now = utcnow()
    await db.assignments.update_one(
        {"_id": to_object_id(assignment_id), "owner_id": user["id"]},
        {
            "$set": {
                "status": AssignmentStatus.ready.value,
                "completed_at": None,
                "updated_at": now,
            }
        },
    )
    updated = serialize_document(
        await db.assignments.find_one({"_id": to_object_id(assignment_id)})
    )
    attempts = await _assignment_attempts(db, assignment_id, user["id"])
    return _assignment_response(updated, attempts[0] if attempts else None, attempts)


@router.post("/{assignment_id}/submit", response_model=AssignmentAttemptResponse)
async def submit_assignment(
    request: Request,
    assignment_id: str,
    payload: AssignmentSubmissionRequest,
    user=Depends(get_current_user),
    db=Depends(get_database),
) -> AssignmentAttemptResponse:
    assignment_doc = await _get_owned_assignment(db, user["id"], assignment_id)
    assignment = _assignment_response(assignment_doc, None)
    if assignment.status != AssignmentStatus.ready.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only ready assignments can be submitted.",
        )
    answer_map = {answer.question_id for answer in payload.answers}
    question_ids = {question.id for question in assignment.questions}
    if question_ids != answer_map:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="All assignment questions must be answered exactly once.",
        )
    try:
        grade_payload = await request.app.state.ai_service.grade_assignment(
            assignment, payload
        )
    except Exception as exc:  # pragma: no cover - defensive runtime path
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Assignment grading failed. {exc}",
        ) from exc
    graded_answers: list[GradedAnswerResponse] = []
    submission_lookup = {
        answer.question_id: answer.answer for answer in payload.answers
    }
    for decision in grade_payload.graded_answers:
        graded_answers.append(
            GradedAnswerResponse(
                question_id=decision.question_id,
                answer=submission_lookup[decision.question_id],
                expected_answer=decision.expected_answer,
                is_correct=decision.is_correct,
                score=decision.score,
                feedback=decision.feedback,
            )
        )
    overall_score = sum(item.score for item in graded_answers) / max(
        len(graded_answers), 1
    )
    now = utcnow()
    document = {
        "assignment_id": assignment_id,
        "owner_id": user["id"],
        "answers": [answer.model_dump() for answer in payload.answers],
        "graded_answers": [answer.model_dump() for answer in graded_answers],
        "score": overall_score,
        "feedback": grade_payload.overall_feedback,
        "completed_at": now,
        "created_at": now,
    }
    result = await db.assignment_attempts.insert_one(document)
    await db.assignments.update_one(
        {"_id": to_object_id(assignment_id), "owner_id": user["id"]},
        {
            "$set": {
                "status": AssignmentStatus.completed.value,
                "completed_at": now,
                "updated_at": now,
            }
        },
    )
    created = await db.assignment_attempts.find_one({"_id": result.inserted_id})
    return AssignmentAttemptResponse.model_validate(serialize_document(created))
