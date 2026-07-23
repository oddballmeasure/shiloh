"use client";

import { useEffect, useState } from "react";

import { InlineMessage } from "@/components/inline-message";
import { fetchJson, fetchVoid, getErrorMessage } from "@/lib/client-api";
import type { Flashcard, FlashcardDifficulty, FlashcardSet, StudySession } from "@/lib/types";

export function StudySessionView({
  flashcardSet,
  initialSession,
}: {
  flashcardSet: FlashcardSet;
  initialSession: StudySession;
}) {
  const [session, setSession] = useState(initialSession);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [starSaving, setStarSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentCard = session.flashcards[index];

  useEffect(() => {
    setRevealed(false);
  }, [currentCard?.id]);

  async function reloadSession() {
    try {
      const payload = await fetchJson<StudySession>(
        `/api/proxy/api/flashcard-sets/${flashcardSet.id}/study-session`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ limit: 20 }),
        },
      );
      setSession(payload);
      setIndex(0);
      setError(null);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to refresh the study queue."));
    }
  }

  async function reviewCard(difficulty: FlashcardDifficulty) {
    if (!currentCard) {
      return;
    }
    setSaving(true);
    try {
      await fetchVoid(`/api/proxy/api/flashcards/${currentCard.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ difficulty }),
      });
      setIndex((value) => value + 1);
      setError(null);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to record the flashcard review."));
    } finally {
      setSaving(false);
    }
  }

  async function toggleStar() {
    if (!currentCard) {
      return;
    }
    setStarSaving(true);
    try {
      const updated = await fetchJson<Flashcard>(`/api/proxy/api/flashcards/${currentCard.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ starred: !currentCard.starred }),
      });
      setSession((current) => ({
        ...current,
        flashcards: current.flashcards.map((card) => (card.id === updated.id ? updated : card)),
      }));
      setError(null);
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Unable to update the flashcard star."));
    } finally {
      setStarSaving(false);
    }
  }

  return (
    <section className="panel">
      <div className="row-between">
        <div>
          <h2>{flashcardSet.name}</h2>
          <p className="subtle">Set status: {session.set_status}</p>
        </div>
        <button className="ghost-button" onClick={reloadSession}>
          Refresh Queue
        </button>
      </div>
      {error ? <InlineMessage>{error}</InlineMessage> : null}

      {!currentCard ? (
        <div className="empty-state">
          <h3>Session complete</h3>
          <p className="subtle">Refresh the queue to study the weighted order again.</p>
        </div>
      ) : (
        <div className="study-card-shell">
          <div className="study-card-actions">
            <button
              aria-label={currentCard.starred ? "Remove star from flashcard" : "Star flashcard"}
              aria-pressed={currentCard.starred}
              className={`study-star-button${currentCard.starred ? " is-starred" : ""}`}
              disabled={starSaving}
              onClick={toggleStar}
              type="button"
            >
              {currentCard.starred ? "Starred" : "Star"}
            </button>
          </div>
          <button
            aria-expanded={revealed}
            className={`study-card-face${revealed ? " is-revealed" : ""}`}
            onClick={() => setRevealed((value) => !value)}
            type="button"
          >
            {revealed ? (
              <span className="study-card-details">
                <span className="study-card-term">{currentCard.korean}</span>
                <span><strong>English:</strong> {currentCard.english}</span>
                {currentCard.notes ? <span><strong>Notes:</strong> {currentCard.notes}</span> : null}
                {currentCard.example ? <span><strong>Example:</strong> {currentCard.example}</span> : null}
                <span><strong>Difficulty:</strong> {currentCard.difficulty}</span>
                <span><strong>Reviews:</strong> {currentCard.correct_reviews} correct, {currentCard.incorrect_reviews} hard</span>
                {currentCard.last_reviewed_at ? (
                  <span><strong>Last reviewed:</strong> {new Date(currentCard.last_reviewed_at).toLocaleString()}</span>
                ) : null}
                {currentCard.tags.length > 0 ? (
                  <span className="tag-row">{currentCard.tags.map((tag) => `#${tag}`).join(" ")}</span>
                ) : null}
                <span className="study-card-hint">Click to show Korean only</span>
              </span>
            ) : (
              <span className="study-card-front">
                <span className="study-card-term">{currentCard.korean}</span>
                <span className="study-card-hint">Click to reveal details</span>
              </span>
            )}
          </button>
          <div className="button-row">
            <button className="danger-button" disabled={saving} onClick={() => reviewCard("hard")}>
              Mark Hard
            </button>
            <button className="ghost-button" disabled={saving} onClick={() => reviewCard("medium")}>
              Mark Medium
            </button>
            <button className="primary-button" disabled={saving} onClick={() => reviewCard("easy")}>
              Mark Easy
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
