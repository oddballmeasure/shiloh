"use client";

import { useEffect, useState } from "react";

import { InlineMessage } from "@/components/inline-message";
import { MessageBanner } from "@/components/message-banner";
import { fetchJson, getErrorMessage } from "@/lib/client-api";
import type { Assignment, AssignmentAttempt } from "@/lib/types";

function assignmentDescription(assignment: Assignment): string | null {
  const instructions = assignment.instructions?.trim();
  if (!instructions) {
    return null;
  }

  const lines = instructions
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const titleLine = `assignment title: ${assignment.title}`.toLowerCase();

  if (lines[0]?.toLowerCase() === titleLine) {
    const trimmed = lines.slice(1).join("\n");
    return trimmed || null;
  }

  return instructions;
}

export function AssignmentWorkspace({ assignment }: { assignment: Assignment }) {
  const [currentAssignment, setCurrentAssignment] = useState(assignment);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [attempt, setAttempt] = useState<AssignmentAttempt | null>(assignment.latest_attempt);
  const [error, setError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reopening, setReopening] = useState(false);
  const isCompleted = currentAssignment.status === "completed";
  const description = assignmentDescription(currentAssignment);

  useEffect(() => {
    if (currentAssignment.status !== "completed") {
      return;
    }
    setAnswers((current) =>
      Object.fromEntries(currentAssignment.questions.map((question) => {
        const attemptedAnswer = attempt?.answers.find((answer) => answer.question_id === question.id);
        return [question.id, attemptedAnswer?.answer ?? current[question.id] ?? ""];
      })),
    );
  }, [attempt, currentAssignment.questions, currentAssignment.status]);

  useEffect(() => {
    if (currentAssignment.status !== "processing") {
      return;
    }

    let cancelled = false;

    const refreshAssignment = async () => {
      try {
        const nextAssignment = await fetchJson<Assignment>(
          `/api/proxy/api/assignments/${currentAssignment.id}`,
        );
        if (!cancelled) {
          setCurrentAssignment(nextAssignment);
          setAttempt(nextAssignment.latest_attempt);
          setStatusError(null);
        }
      } catch (refreshError) {
        if (!cancelled) {
          setStatusError(getErrorMessage(refreshError, "Unable to refresh the assignment status."));
        }
      }
    };

    void refreshAssignment();
    const intervalId = window.setInterval(() => {
      void refreshAssignment();
    }, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [currentAssignment.id, currentAssignment.status]);

  async function submitAssignment() {
    const unanswered = currentAssignment.questions.filter(
      (question) => !(answers[question.id] ?? "").trim(),
    );
    if (unanswered.length > 0) {
      setError("Answer every question before submitting the assignment.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = await fetchJson<AssignmentAttempt>(
        `/api/proxy/api/assignments/${currentAssignment.id}/submit`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            answers: currentAssignment.questions.map((question) => ({
              question_id: question.id,
              answer: answers[question.id] ?? "",
            })),
          }),
        },
      );
      setAttempt(payload);
      setCurrentAssignment((current) => ({
        ...current,
        status: "completed",
        completed_at: payload.completed_at,
        latest_attempt: payload,
        attempts: [payload, ...current.attempts],
        updated_at: payload.completed_at,
      }));
      setError(null);
    } catch (submitError) {
      setError(getErrorMessage(submitError, "Unable to submit the assignment."));
    } finally {
      setSubmitting(false);
    }
  }

  async function redoAssignment() {
    setReopening(true);
    setError(null);
    try {
      const reopened = await fetchJson<Assignment>(
        `/api/proxy/api/assignments/${currentAssignment.id}/redo`,
        { method: "POST" },
      );
      setCurrentAssignment(reopened);
      setAttempt(reopened.latest_attempt);
      setAnswers(Object.fromEntries(reopened.questions.map((question) => [question.id, ""])));
    } catch (redoError) {
      setError(getErrorMessage(redoError, "Unable to reopen the assignment."));
    } finally {
      setReopening(false);
    }
  }

  if (currentAssignment.status !== "ready" && currentAssignment.status !== "completed") {
    return (
      <section className="panel">
        <div className="row-between">
          <h2>{currentAssignment.title}</h2>
          <span className={`status-pill ${currentAssignment.status}`}>{currentAssignment.status}</span>
        </div>
        <details className="assignment-description">
          <summary>Advanced Description</summary>
          <div className="stack">
            <p className="subtle">{description || "No additional instructions were provided."}</p>
            <p className="subtle">Level: {currentAssignment.target_level}</p>
            <p className="subtle">Extraction: {currentAssignment.source_extraction_status}</p>
            {currentAssignment.source_file ? (
              <p>
                <a
                  className="ghost-button"
                  href={`/api/proxy/api/assignments/${currentAssignment.id}/source-file`}
                  target="_blank"
                  rel="noreferrer"
                >
                  View Submitted PDF
                </a>
              </p>
            ) : null}
          </div>
        </details>
        {currentAssignment.status === "processing" ? (
          <p className="subtle">This assignment is still being generated. Status refreshes automatically.</p>
        ) : null}
        {currentAssignment.generation_error ? (
          <p className="error-text">{currentAssignment.generation_error}</p>
        ) : null}
        {currentAssignment.generation_failures.length > 0 ? (
          <div className="stack">
            {currentAssignment.generation_failures.map((failure, index) => (
              <article className="card" key={`${failure.occurred_at}-${index}`}>
                <p className="error-text">
                  {failure.stage === "extraction" ? "Extraction failed" : "Generation failed"}:{" "}
                  {failure.message}
                </p>
                <p className="subtle">{new Date(failure.occurred_at).toLocaleString()}</p>
              </article>
            ))}
          </div>
        ) : null}
        {statusError ? <MessageBanner>{statusError}</MessageBanner> : null}
      </section>
    );
  }

  return (
    <div className="grid">
      <section className="panel">
        <div className="row-between">
          <div className="stack stack-tight">
            <h2>{currentAssignment.title}</h2>
            <p className="subtle">
              {currentAssignment.target_level} · {currentAssignment.source}
            </p>
          </div>
          <span className={`status-pill ${currentAssignment.status}`}>{currentAssignment.status}</span>
        </div>
        <details className="assignment-description">
          <summary>Advanced Description</summary>
          <div className="stack">
            <p className="subtle">{description || "No additional instructions were provided."}</p>
            {currentAssignment.completed_at ? (
              <p className="subtle">
                Completed: {new Date(currentAssignment.completed_at).toLocaleString()}
              </p>
            ) : null}
            {currentAssignment.source_file ? (
              <p>
                <a
                  className="ghost-button"
                  href={`/api/proxy/api/assignments/${currentAssignment.id}/source-file`}
                  target="_blank"
                  rel="noreferrer"
                >
                  View Submitted PDF
                </a>
              </p>
            ) : null}
          </div>
        </details>
        <div className="assignment-question-section stack">
          {currentAssignment.questions.map((question) => (
            <label className="question-block" key={question.id}>
              <span>{question.prompt}</span>
              {question.type === "multiple_choice" ? (
                <select
                  disabled={isCompleted}
                  value={answers[question.id] ?? ""}
                  onChange={(event) =>
                    setAnswers({ ...answers, [question.id]: event.target.value })
                  }
                >
                  <option value="">Select an answer</option>
                  {question.options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              ) : (
                <textarea
                  disabled={isCompleted}
                  rows={3}
                  value={answers[question.id] ?? ""}
                  onChange={(event) =>
                    setAnswers({ ...answers, [question.id]: event.target.value })
                  }
                />
              )}
            </label>
          ))}
          {isCompleted ? (
            <div className="stack stack-tight">
              <InlineMessage tone="success">This assignment has been completed.</InlineMessage>
              <button className="primary-button" disabled={reopening} onClick={redoAssignment}>
                {reopening ? "Reopening..." : "Redo Assignment"}
              </button>
            </div>
          ) : (
            <button className="primary-button" disabled={submitting} onClick={submitAssignment}>
              {submitting ? "Submitting..." : "Submit Assignment"}
            </button>
          )}
          {error ? <InlineMessage>{error}</InlineMessage> : null}
          {statusError ? <MessageBanner>{statusError}</MessageBanner> : null}
        </div>
      </section>

      <section className="panel">
        <h2>Latest Result</h2>
        {attempt ? (
          <div className="stack">
            <p>
              Score: <strong>{Math.round(attempt.score * 100)}%</strong>
            </p>
            <p className="subtle">{attempt.feedback}</p>
            {attempt.graded_answers.map((answer) => (
              <article className="card" key={answer.question_id}>
                <p>
                  <strong>Your answer:</strong> {answer.answer}
                </p>
                <p>
                  <strong>Expected:</strong> {answer.expected_answer}
                </p>
                <p className={answer.is_correct ? "success-text" : "error-text"}>{answer.feedback}</p>
              </article>
            ))}
          </div>
        ) : (
          <p className="subtle">No submission yet.</p>
        )}
      </section>

      <section className="panel full-span">
        <h2>Grading History</h2>
        {currentAssignment.attempts.length > 0 ? (
          <div className="stack">
            {currentAssignment.attempts.map((historyAttempt) => (
              <article className="card" key={historyAttempt.id}>
                <p>
                  <strong>{Math.round(historyAttempt.score * 100)}%</strong> ·{" "}
                  {new Date(historyAttempt.completed_at).toLocaleString()}
                </p>
                <p className="subtle">{historyAttempt.feedback}</p>
                {historyAttempt.graded_answers.map((answer) => (
                  <div className="stack stack-tight" key={answer.question_id}>
                    <p><strong>Your answer:</strong> {answer.answer}</p>
                    <p><strong>Expected:</strong> {answer.expected_answer}</p>
                    <p className={answer.is_correct ? "success-text" : "error-text"}>{answer.feedback}</p>
                  </div>
                ))}
              </article>
            ))}
          </div>
        ) : (
          <p className="subtle">Your graded attempts will appear here.</p>
        )}
      </section>
    </div>
  );
}
