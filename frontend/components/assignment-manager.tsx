"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { InlineMessage } from "@/components/inline-message";
import { MessageBanner } from "@/components/message-banner";
import { fetchJson, fetchVoid, getErrorMessage } from "@/lib/client-api";
import type { Assignment, AssignmentGenerationFailure, KoreanLevel, QuestionType } from "@/lib/types";

type ManualQuestionDraft = {
  id: string;
  type: QuestionType;
  prompt: string;
  options: string;
  correct_answer: string;
  accepted_answers: string;
  explanation: string;
};

function emptyManualQuestion(index: number): ManualQuestionDraft {
  return {
    id: `manual-${index}`,
    type: "multiple_choice",
    prompt: "",
    options: "",
    correct_answer: "",
    accepted_answers: "",
    explanation: "",
  };
}

type ManualQuestionValidation = {
  prompt?: string;
  options?: string;
  correct_answer?: string;
};

type ManualValidationState = {
  formError: string | null;
  questionErrors: Record<string, ManualQuestionValidation>;
};

type AssignmentView = "all" | "available" | "create";

function latestFailure(assignment: Assignment): AssignmentGenerationFailure | null {
  return assignment.generation_failures[assignment.generation_failures.length - 1] ?? null;
}

function parseDelimitedList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function validateTextForm(form: {
  title: string;
  source_text: string;
}): string | null {
  if (!form.title.trim()) {
    return "Enter a title before generating an assignment.";
  }
  if (!form.source_text.trim()) {
    return "Add source text before generating an assignment.";
  }
  return null;
}

function validatePdfForm(form: {
  title: string;
  file: File | null;
}): string | null {
  if (!form.title.trim()) {
    return "Enter a title before generating an assignment.";
  }
  if (!form.file) {
    return "Choose a PDF before generating an assignment.";
  }
  const filename = form.file.name.toLowerCase();
  if (form.file.type !== "application/pdf" && !filename.endsWith(".pdf")) {
    return "Only PDF uploads are supported.";
  }
  return null;
}

function validateManualForm(form: {
  title: string;
  questions: ManualQuestionDraft[];
}): ManualValidationState {
  if (!form.title.trim()) {
    return {
      formError: "Enter a title before saving the manual assignment.",
      questionErrors: {},
    };
  }
  if (form.questions.length === 0) {
    return {
      formError: "Add at least one question before saving the manual assignment.",
      questionErrors: {},
    };
  }

  const questionErrors: Record<string, ManualQuestionValidation> = {};

  for (const [index, question] of form.questions.entries()) {
    const errors: ManualQuestionValidation = {};
    const options = parseDelimitedList(question.options);

    if (!question.prompt.trim()) {
      errors.prompt = `Question ${index + 1} needs a prompt.`;
    }
    if (!question.correct_answer.trim()) {
      errors.correct_answer = `Question ${index + 1} needs a correct answer.`;
    }
    if (question.type === "multiple_choice" && options.length < 2) {
      errors.options = `Question ${index + 1} needs at least two options.`;
    }
    if (question.type !== "multiple_choice" && options.length > 0) {
      errors.options = `Question ${index + 1} can only use options when it is multiple choice.`;
    }

    if (Object.keys(errors).length > 0) {
      questionErrors[question.id] = errors;
    }
  }

  if (Object.keys(questionErrors).length > 0) {
    return {
      formError: "Fix the highlighted manual assignment fields and try again.",
      questionErrors,
    };
  }

  return { formError: null, questionErrors: {} };
}

export function AssignmentManager({
  initialAssignments,
  initialView = "all",
}: {
  initialAssignments: Assignment[];
  initialView?: AssignmentView;
}) {
  const [assignments, setAssignments] = useState(initialAssignments);
  const [view, setView] = useState<AssignmentView>(initialView);
  const [textForm, setTextForm] = useState({
    title: "",
    target_level: "beginner" as KoreanLevel,
    source_text: "",
    study_context: "",
  });
  const [pdfForm, setPdfForm] = useState({
    title: "",
    target_level: "beginner" as KoreanLevel,
    study_context: "",
    file: null as File | null,
  });
  const [manualForm, setManualForm] = useState({
    title: "",
    instructions: "",
    target_level: "beginner" as KoreanLevel,
    questions: [emptyManualQuestion(0)],
  });
  const [textError, setTextError] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [manualError, setManualError] = useState<string | null>(null);
  const [manualQuestionErrors, setManualQuestionErrors] = useState<
    Record<string, ManualQuestionValidation>
  >({});
  const [listError, setListError] = useState<string | null>(null);
  const [creatingText, setCreatingText] = useState(false);
  const [creatingPdf, setCreatingPdf] = useState(false);
  const [creatingManual, setCreatingManual] = useState(false);
  const [deletingAssignmentId, setDeletingAssignmentId] = useState<string | null>(null);
  const [pdfInputKey, setPdfInputKey] = useState(0);

  const hasProcessingAssignments = assignments.some((assignment) => assignment.status === "processing");
  const visibleAssignments = assignments.filter(
    (assignment) => view !== "available" || assignment.status !== "completed",
  );

  useEffect(() => {
    if (!hasProcessingAssignments) {
      return;
    }

    let cancelled = false;

    const refreshAssignments = async () => {
      try {
        const latestAssignments = await fetchJson<Assignment[]>("/api/proxy/api/assignments");
        if (!cancelled) {
          setAssignments(latestAssignments);
          setListError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setListError(getErrorMessage(error));
        }
      }
    };

    void refreshAssignments();
    const intervalId = window.setInterval(() => {
      void refreshAssignments();
    }, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [hasProcessingAssignments]);

  async function createAiTextAssignment() {
    const validationError = validateTextForm(textForm);
    if (validationError) {
      setTextError(validationError);
      return;
    }
    setCreatingText(true);
    setTextError(null);
    try {
      const created = await fetchJson<Assignment>("/api/proxy/api/assignments/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(textForm),
      });
      setAssignments((current) => [created, ...current]);
      setView("all");
      setTextForm({
        title: "",
        target_level: "beginner",
        source_text: "",
        study_context: "",
      });
    } catch (error) {
      setTextError(getErrorMessage(error, "Unable to generate an assignment from text."));
    } finally {
      setCreatingText(false);
    }
  }

  async function createAiPdfAssignment() {
    const validationError = validatePdfForm(pdfForm);
    if (validationError) {
      setPdfError(validationError);
      return;
    }
    const file = pdfForm.file;
    if (!file) {
      setPdfError("Choose a PDF before generating an assignment.");
      return;
    }

    setCreatingPdf(true);
    setPdfError(null);
    try {
      const formData = new FormData();
      formData.append("title", pdfForm.title);
      formData.append("target_level", pdfForm.target_level);
      formData.append("study_context", pdfForm.study_context);
      formData.append("file", file);
      const created = await fetchJson<Assignment>("/api/proxy/api/assignments/generate-from-pdf", {
        method: "POST",
        body: formData,
      });
      setAssignments((current) => [created, ...current]);
      setView("all");
      setPdfForm({
        title: "",
        target_level: "beginner",
        study_context: "",
        file: null,
      });
      setPdfInputKey((current) => current + 1);
    } catch (error) {
      setPdfError(getErrorMessage(error, "Unable to generate an assignment from the PDF."));
    } finally {
      setCreatingPdf(false);
    }
  }

  async function createManualAssignment() {
    const validation = validateManualForm(manualForm);
    if (validation.formError) {
      setManualError(validation.formError);
      setManualQuestionErrors(validation.questionErrors);
      return;
    }

    setCreatingManual(true);
    setManualError(null);
    setManualQuestionErrors({});
    try {
      const created = await fetchJson<Assignment>("/api/proxy/api/assignments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: "manual",
          title: manualForm.title,
          instructions: manualForm.instructions,
          target_level: manualForm.target_level,
          questions: manualForm.questions.map((question) => ({
            type: question.type,
            prompt: question.prompt,
            options: question.type === "multiple_choice" ? parseDelimitedList(question.options) : [],
            correct_answer: question.correct_answer,
            accepted_answers: parseDelimitedList(question.accepted_answers),
            explanation: question.explanation || null,
          })),
        }),
      });
      setAssignments((current) => [created, ...current]);
      setView("all");
      setManualForm({
        title: "",
        instructions: "",
        target_level: "beginner",
        questions: [emptyManualQuestion(0)],
      });
      setManualQuestionErrors({});
    } catch (error) {
      setManualError(getErrorMessage(error, "Unable to save the manual assignment."));
    } finally {
      setCreatingManual(false);
    }
  }

  async function deleteAssignment(id: string) {
    setDeletingAssignmentId(id);
    setListError(null);
    try {
      await fetchVoid(`/api/proxy/api/assignments/${id}`, {
        method: "DELETE",
      });
      setAssignments((current) => current.filter((assignment) => assignment.id !== id));
    } catch (error) {
      setListError(getErrorMessage(error, "Unable to delete the assignment."));
    } finally {
      setDeletingAssignmentId(null);
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="row-between">
          <div>
            <h2>Assignment Workspace</h2>
            <p className="subtle">Create new work or focus on available assignments that still need attention.</p>
          </div>
          <div className="button-row view-switcher">
            <button
              className={view === "all" ? "primary-button" : "ghost-button"}
              onClick={() => setView("all")}
              type="button"
            >
              All Assignments
            </button>
            <button
              className={view === "available" ? "primary-button" : "ghost-button"}
              onClick={() => setView("available")}
              type="button"
            >
              Available
            </button>
            <button
              className={view === "create" ? "primary-button" : "ghost-button"}
              onClick={() => setView("create")}
              type="button"
            >
              Create
            </button>
          </div>
        </div>
      </section>

      {view !== "available" ? (
        <div className="grid">
          <section className="panel">
            <h2>Generate From Text</h2>
            <div className="form-grid">
              <label>
                Title
                <input
                  value={textForm.title}
                  onChange={(event) => setTextForm({ ...textForm, title: event.target.value })}
                />
              </label>
              <label>
                Level
                <select
                  value={textForm.target_level}
                  onChange={(event) =>
                    setTextForm({ ...textForm, target_level: event.target.value as KoreanLevel })
                  }
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </label>
              <label>
                Source Text
                <textarea
                  rows={6}
                  value={textForm.source_text}
                  onChange={(event) => setTextForm({ ...textForm, source_text: event.target.value })}
                />
              </label>
              <label>
                Optional Study Context
                <textarea
                  rows={3}
                  value={textForm.study_context}
                  onChange={(event) =>
                    setTextForm({ ...textForm, study_context: event.target.value })
                  }
                  placeholder="Vocabulary focus, worksheet context, or lesson notes"
                />
              </label>
              <button className="primary-button" disabled={creatingText} onClick={createAiTextAssignment}>
                {creatingText ? "Generating..." : "Generate From Text"}
              </button>
              {textError ? <InlineMessage>{textError}</InlineMessage> : null}
            </div>
          </section>

          <section className="panel">
            <h2>Generate From PDF</h2>
            <div className="form-grid">
              <label>
                Title
                <input
                  value={pdfForm.title}
                  onChange={(event) => setPdfForm({ ...pdfForm, title: event.target.value })}
                />
              </label>
              <label>
                Level
                <select
                  value={pdfForm.target_level}
                  onChange={(event) =>
                    setPdfForm({ ...pdfForm, target_level: event.target.value as KoreanLevel })
                  }
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </label>
              <label>
                Optional Study Context
                <textarea
                  rows={3}
                  value={pdfForm.study_context}
                  onChange={(event) =>
                    setPdfForm({ ...pdfForm, study_context: event.target.value })
                  }
                  placeholder="Vocabulary focus, worksheet context, or lesson notes"
                />
              </label>
              <label>
                PDF File
                <input
                  key={pdfInputKey}
                  type="file"
                  accept="application/pdf"
                  onChange={(event) =>
                    setPdfForm({ ...pdfForm, file: event.target.files?.[0] ?? null })
                  }
                />
              </label>
              <button className="primary-button" disabled={creatingPdf} onClick={createAiPdfAssignment}>
                {creatingPdf ? "Generating..." : "Generate From PDF"}
              </button>
              {pdfError ? <InlineMessage>{pdfError}</InlineMessage> : null}
            </div>
          </section>

          <section className="panel">
            <h2>Create Manual Assignment</h2>
            <div className="form-grid">
              <label>
                Title
                <input
                  value={manualForm.title}
                  onChange={(event) => setManualForm({ ...manualForm, title: event.target.value })}
                />
              </label>
              <label>
                Level
                <select
                  value={manualForm.target_level}
                  onChange={(event) =>
                    setManualForm({ ...manualForm, target_level: event.target.value as KoreanLevel })
                  }
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="advanced">Advanced</option>
                </select>
              </label>
              <label>
                Instructions
                <textarea
                  rows={3}
                  value={manualForm.instructions}
                  onChange={(event) =>
                    setManualForm({ ...manualForm, instructions: event.target.value })
                  }
                />
              </label>
              {manualForm.questions.map((question, index) => (
                <div className="question-draft" key={question.id}>
                  <label>
                    Prompt
                    <input
                      value={question.prompt}
                      onChange={(event) =>
                        setManualForm({
                          ...manualForm,
                          questions: manualForm.questions.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, prompt: event.target.value } : item,
                          ),
                        })
                      }
                    />
                    {manualQuestionErrors[question.id]?.prompt ? (
                      <InlineMessage>{manualQuestionErrors[question.id].prompt}</InlineMessage>
                    ) : null}
                  </label>
                  <label>
                    Type
                    <select
                      value={question.type}
                      onChange={(event) =>
                        setManualForm({
                          ...manualForm,
                          questions: manualForm.questions.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, type: event.target.value as QuestionType }
                              : item,
                          ),
                        })
                      }
                    >
                      <option value="multiple_choice">Multiple Choice</option>
                      <option value="fill_blank">Fill In The Blank</option>
                      <option value="short_answer">Short Answer</option>
                    </select>
                  </label>
                  <label>
                    Options
                    <input
                      value={question.options}
                      onChange={(event) =>
                        setManualForm({
                          ...manualForm,
                          questions: manualForm.questions.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, options: event.target.value } : item,
                          ),
                        })
                      }
                      placeholder="Only used for multiple choice"
                    />
                    {manualQuestionErrors[question.id]?.options ? (
                      <InlineMessage>{manualQuestionErrors[question.id].options}</InlineMessage>
                    ) : null}
                  </label>
                  <label>
                    Correct Answer
                    <input
                      value={question.correct_answer}
                      onChange={(event) =>
                        setManualForm({
                          ...manualForm,
                          questions: manualForm.questions.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, correct_answer: event.target.value }
                              : item,
                          ),
                        })
                      }
                    />
                    {manualQuestionErrors[question.id]?.correct_answer ? (
                      <InlineMessage>{manualQuestionErrors[question.id].correct_answer}</InlineMessage>
                    ) : null}
                  </label>
                  <label>
                    Accepted Answers
                    <input
                      value={question.accepted_answers}
                      onChange={(event) =>
                        setManualForm({
                          ...manualForm,
                          questions: manualForm.questions.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, accepted_answers: event.target.value }
                              : item,
                          ),
                        })
                      }
                    />
                  </label>
                  <label>
                    Explanation
                    <textarea
                      rows={2}
                      value={question.explanation}
                      onChange={(event) =>
                        setManualForm({
                          ...manualForm,
                          questions: manualForm.questions.map((item, itemIndex) =>
                            itemIndex === index
                              ? { ...item, explanation: event.target.value }
                              : item,
                          ),
                        })
                      }
                    />
                  </label>
                </div>
              ))}
              <div className="button-row">
                <button
                  className="ghost-button"
                  onClick={() =>
                    setManualForm({
                      ...manualForm,
                      questions: [...manualForm.questions, emptyManualQuestion(manualForm.questions.length)],
                    })
                  }
                  type="button"
                >
                  Add Question
                </button>
                <button className="primary-button" disabled={creatingManual} onClick={createManualAssignment}>
                  {creatingManual ? "Saving..." : "Save Manual Assignment"}
                </button>
              </div>
              {manualError ? <InlineMessage>{manualError}</InlineMessage> : null}
            </div>
          </section>
        </div>
      ) : null}

      <section className="panel">
        <div className="row-between">
          <div>
            <h2>{view === "available" ? "Available Assignments" : "Assignments"}</h2>
            <p className="subtle">
              {view === "available"
                ? "Assignments that are still in progress, ready to complete, or need review."
                : "Open, review, or delete your assignment history."}
            </p>
          </div>
          {hasProcessingAssignments ? (
            <p className="subtle">Assignments in progress refresh automatically.</p>
          ) : null}
        </div>
        {listError ? <MessageBanner>{listError}</MessageBanner> : null}
        <div className="stack">
          {visibleAssignments.map((assignment) => {
            const failure = latestFailure(assignment);

            return (
              <article className="card" key={assignment.id}>
                <div className="row-between">
                  <div>
                    <h3>{assignment.title}</h3>
                    <p className="subtle">
                      {assignment.source} · {assignment.target_level} · {assignment.status}
                    </p>
                    {assignment.source_file ? (
                      <p className="subtle">
                        PDF: {assignment.source_file.filename} ({assignment.source_file.size_bytes} bytes)
                      </p>
                    ) : null}
                    {assignment.status === "processing" ? (
                      <p className="subtle">
                        Generation is still running. This page will refresh the assignment automatically.
                      </p>
                    ) : null}
                    {failure ? (
                      <>
                        <p className="error-text">
                          {failure.stage === "extraction" ? "Extraction failed" : "Generation failed"}:{" "}
                          {failure.message}
                        </p>
                        <p className="subtle">
                          Last failure: {new Date(failure.occurred_at).toLocaleString()}
                        </p>
                      </>
                    ) : null}
                  </div>
                  <div className="button-row">
                    <Link className="ghost-button" href={`/assignments/${assignment.id}`}>
                      {assignment.status === "completed" ? "View Result" : "Open"}
                    </Link>
                    <button
                      className="danger-button"
                      disabled={deletingAssignmentId === assignment.id}
                      onClick={() => deleteAssignment(assignment.id)}
                    >
                      {deletingAssignmentId === assignment.id ? "Deleting..." : "Delete"}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
          {visibleAssignments.length === 0 ? (
            <p className="subtle">
              {view === "available"
                ? "No incomplete assignments are waiting right now."
                : "No assignments yet."}
            </p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
