"use client";

import { useEffect, useMemo, useState } from "react";

import { InlineMessage } from "@/components/inline-message";
import { MessageBanner } from "@/components/message-banner";
import { fetchJson, fetchVoid, getErrorMessage } from "@/lib/client-api";
import type { Flashcard, FlashcardDifficulty, FlashcardSet } from "@/lib/types";

function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function FlashcardSetDetail({
  initialSet,
  initialFlashcards,
}: {
  initialSet: FlashcardSet;
  initialFlashcards: Flashcard[];
}) {
  const [flashcardSet, setFlashcardSet] = useState(initialSet);
  const [flashcards, setFlashcards] = useState(initialFlashcards);
  const [setError, setSetError] = useState<string | null>(null);
  const [cardError, setCardError] = useState<string | null>(null);
  const [newCard, setNewCard] = useState({
    korean: "",
    english: "",
    notes: "",
    example: "",
    difficulty: "medium" as FlashcardDifficulty,
    tags: "",
  });
  const isEditable = flashcardSet.status === "active" || flashcardSet.status === "done";

  const sortedFlashcards = useMemo(
    () => [...flashcards].sort((left, right) => right.updated_at.localeCompare(left.updated_at)),
    [flashcards],
  );

  useEffect(() => {
    if (flashcardSet.status !== "processing") {
      return;
    }

    let cancelled = false;

    const refreshSet = async () => {
      try {
        const latestSet = await fetchJson<FlashcardSet>(`/api/proxy/api/flashcard-sets/${flashcardSet.id}`);
        if (cancelled) {
          return;
        }
        setFlashcardSet(latestSet);
        if (latestSet.status === "active" || latestSet.status === "done") {
          const latestCards = await fetchJson<Flashcard[]>(
            `/api/proxy/api/flashcard-sets/${flashcardSet.id}/flashcards`,
          );
          if (!cancelled) {
            setFlashcards(latestCards);
          }
        }
        setSetError(null);
      } catch (requestError) {
        if (!cancelled) {
          setSetError(getErrorMessage(requestError, "Unable to refresh the flashcard set."));
        }
      }
    };

    void refreshSet();
    const intervalId = window.setInterval(() => {
      void refreshSet();
    }, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [flashcardSet.id, flashcardSet.status]);

  async function updateSet() {
    try {
      const updated = await fetchJson<FlashcardSet>(`/api/proxy/api/flashcard-sets/${flashcardSet.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: flashcardSet.name,
          description: flashcardSet.description,
          tags: flashcardSet.tags,
        }),
      });
      setFlashcardSet(updated);
      setSetError(null);
    } catch (requestError) {
      setSetError(getErrorMessage(requestError, "Unable to update the flashcard set."));
    }
  }

  async function createFlashcard() {
    try {
      const created = await fetchJson<Flashcard>(
        `/api/proxy/api/flashcard-sets/${flashcardSet.id}/flashcards`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...newCard,
            tags: parseTags(newCard.tags),
          }),
        },
      );
      setFlashcards((current) => [created, ...current]);
      setNewCard({
        korean: "",
        english: "",
        notes: "",
        example: "",
        difficulty: "medium",
        tags: "",
      });
      setCardError(null);
    } catch (requestError) {
      setCardError(getErrorMessage(requestError, "Unable to create the flashcard."));
    }
  }

  async function saveCard(card: Flashcard) {
    try {
      const updated = await fetchJson<Flashcard>(`/api/proxy/api/flashcards/${card.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          korean: card.korean,
          english: card.english,
          notes: card.notes,
          example: card.example,
          difficulty: card.difficulty,
          tags: card.tags,
          starred: card.starred,
        }),
      });
      setFlashcards((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      const currentSet = await fetchJson<FlashcardSet>(
        `/api/proxy/api/flashcard-sets/${flashcardSet.id}`,
      );
      setFlashcardSet(currentSet);
      setCardError(null);
    } catch (requestError) {
      setCardError(getErrorMessage(requestError, "Unable to save the flashcard."));
    }
  }

  async function deleteCard(id: string) {
    try {
      await fetchVoid(`/api/proxy/api/flashcards/${id}`, {
        method: "DELETE",
      });
      setFlashcards((current) => current.filter((item) => item.id !== id));
      setCardError(null);
    } catch (requestError) {
      setCardError(getErrorMessage(requestError, "Unable to delete the flashcard."));
    }
  }

  async function toggleCardStar(card: Flashcard) {
    try {
      const updated = await fetchJson<Flashcard>(`/api/proxy/api/flashcards/${card.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ starred: !card.starred }),
      });
      setFlashcards((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setCardError(null);
    } catch (requestError) {
      setCardError(getErrorMessage(requestError, "Unable to update the flashcard star."));
    }
  }

  return (
    <div className="grid">
      <section className="panel">
        <div className="row-between">
          <div>
            <h2>{flashcardSet.name}</h2>
            <p className="subtle">
              {flashcardSet.source === "ai_list" ? "AI import" : "Manual set"} · {flashcardSet.status}
            </p>
          </div>
          <span className={`status-pill ${flashcardSet.status}`}>{flashcardSet.status}</span>
        </div>
        {setError ? <MessageBanner>{setError}</MessageBanner> : null}
        {flashcardSet.status === "processing" ? (
          <div className="stack">
            <p className="subtle">
              AI is still enriching this set. Card management and study will unlock automatically when
              processing finishes.
            </p>
            {flashcardSet.source_text ? <pre className="json-block">{flashcardSet.source_text}</pre> : null}
          </div>
        ) : null}
        {flashcardSet.status === "failed" ? (
          <div className="stack">
            {flashcardSet.generation_error ? (
              <MessageBanner>{flashcardSet.generation_error}</MessageBanner>
            ) : null}
            {flashcardSet.generation_failures.map((failure, index) => (
              <article className="card" key={`${failure.occurred_at}-${index}`}>
                <p className="error-text">{failure.message}</p>
                <p className="subtle">{new Date(failure.occurred_at).toLocaleString()}</p>
              </article>
            ))}
            {flashcardSet.source_text ? <pre className="json-block">{flashcardSet.source_text}</pre> : null}
          </div>
        ) : null}
        {isEditable ? (
          <div className="form-grid">
            <label>
              Set Name
              <input
                value={flashcardSet.name}
                onChange={(event) => setFlashcardSet({ ...flashcardSet, name: event.target.value })}
              />
            </label>
            <label>
              Description
              <textarea
                value={flashcardSet.description ?? ""}
                onChange={(event) =>
                  setFlashcardSet({ ...flashcardSet, description: event.target.value || null })
                }
                rows={3}
              />
            </label>
            <label>
              Tags
              <input
                value={flashcardSet.tags.join(", ")}
                onChange={(event) =>
                  setFlashcardSet({ ...flashcardSet, tags: parseTags(event.target.value) })
                }
              />
            </label>
            <button className="primary-button" onClick={updateSet}>
              Save Set
            </button>
          </div>
        ) : null}
      </section>

      {isEditable ? (
        <section className="panel">
          <h2>Add Flashcard</h2>
          <div className="form-grid">
            <label>
              Korean
              <input
                value={newCard.korean}
                onChange={(event) => setNewCard({ ...newCard, korean: event.target.value })}
              />
            </label>
            <label>
              English
              <input
                value={newCard.english}
                onChange={(event) => setNewCard({ ...newCard, english: event.target.value })}
              />
            </label>
            <label>
              Notes
              <textarea
                value={newCard.notes}
                onChange={(event) => setNewCard({ ...newCard, notes: event.target.value })}
                rows={2}
              />
            </label>
            <label>
              Example
              <textarea
                value={newCard.example}
                onChange={(event) => setNewCard({ ...newCard, example: event.target.value })}
                rows={2}
              />
            </label>
            <label>
              Difficulty
              <select
                value={newCard.difficulty}
                onChange={(event) =>
                  setNewCard({ ...newCard, difficulty: event.target.value as FlashcardDifficulty })
                }
              >
                <option value="hard">Hard</option>
                <option value="medium">Medium</option>
                <option value="easy">Easy</option>
              </select>
            </label>
            <label>
              Card Tags
              <input
                value={newCard.tags}
                onChange={(event) => setNewCard({ ...newCard, tags: event.target.value })}
              />
            </label>
            <button className="primary-button" onClick={createFlashcard}>
              Add Card
            </button>
            {cardError ? <InlineMessage>{cardError}</InlineMessage> : null}
          </div>
        </section>
      ) : null}

      {isEditable ? (
        <section className="panel full-span">
          <h2>Cards</h2>
          <div className="stack">
            {sortedFlashcards.map((card) => (
              <article className="card" key={card.id}>
                <div className="form-grid compact-grid">
                  <label>
                    Korean
                    <input
                      value={card.korean}
                      onChange={(event) =>
                        setFlashcards(
                          flashcards.map((item) =>
                            item.id === card.id ? { ...item, korean: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </label>
                  <label>
                    English
                    <input
                      value={card.english}
                      onChange={(event) =>
                        setFlashcards(
                          flashcards.map((item) =>
                            item.id === card.id ? { ...item, english: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </label>
                  <label>
                    Difficulty
                    <select
                      value={card.difficulty}
                      onChange={(event) =>
                        setFlashcards(
                          flashcards.map((item) =>
                            item.id === card.id
                              ? { ...item, difficulty: event.target.value as FlashcardDifficulty }
                              : item,
                          ),
                        )
                      }
                    >
                      <option value="hard">Hard</option>
                      <option value="medium">Medium</option>
                      <option value="easy">Easy</option>
                    </select>
                  </label>
                  <label>
                    Tags
                    <input
                      value={card.tags.join(", ")}
                      onChange={(event) =>
                        setFlashcards(
                          flashcards.map((item) =>
                            item.id === card.id
                              ? { ...item, tags: parseTags(event.target.value) }
                              : item,
                          ),
                        )
                      }
                    />
                  </label>
                  <label>
                    Notes
                    <textarea
                      value={card.notes ?? ""}
                      onChange={(event) =>
                        setFlashcards(
                          flashcards.map((item) =>
                            item.id === card.id ? { ...item, notes: event.target.value || null } : item,
                          ),
                        )
                      }
                      rows={2}
                    />
                  </label>
                  <label>
                    Example
                    <textarea
                      value={card.example ?? ""}
                      onChange={(event) =>
                        setFlashcards(
                          flashcards.map((item) =>
                            item.id === card.id ? { ...item, example: event.target.value || null } : item,
                          ),
                        )
                      }
                      rows={2}
                    />
                  </label>
                </div>
                <div className="button-row">
                  <button
                    aria-pressed={card.starred}
                    className={card.starred ? "primary-button" : "ghost-button"}
                    onClick={() => toggleCardStar(card)}
                    type="button"
                  >
                    {card.starred ? "Starred" : "Star"}
                  </button>
                  <button className="ghost-button" onClick={() => saveCard(card)}>
                    Save Card
                  </button>
                  <button className="danger-button" onClick={() => deleteCard(card.id)}>
                    Delete
                  </button>
                </div>
              </article>
            ))}
            {sortedFlashcards.length === 0 ? (
              <p className="subtle">No cards in this set yet.</p>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
