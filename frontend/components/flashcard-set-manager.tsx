"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { InlineMessage } from "@/components/inline-message";
import { MessageBanner } from "@/components/message-banner";
import { fetchJson, fetchVoid, getErrorMessage } from "@/lib/client-api";
import type { FlashcardSet } from "@/lib/types";

function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

type FlashcardView = "sets" | "create";

export function FlashcardSetManager({
  initialSets,
  initialView = "sets",
}: {
  initialSets: FlashcardSet[];
  initialView?: FlashcardView;
}) {
  const router = useRouter();
  const [sets, setSets] = useState(initialSets);
  const [view, setView] = useState<FlashcardView>(initialView);
  const [manualForm, setManualForm] = useState({
    name: "",
    description: "",
    tags: "",
  });
  const [importForm, setImportForm] = useState({
    name: "",
    description: "",
    source_text: "",
  });
  const [manualError, setManualError] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [creatingManual, setCreatingManual] = useState(false);
  const [creatingImport, setCreatingImport] = useState(false);
  const [deletingSetId, setDeletingSetId] = useState<string | null>(null);
  const hasProcessingSets = sets.some((set) => set.status === "processing");

  useEffect(() => {
    if (!hasProcessingSets) {
      return;
    }

    let cancelled = false;

    const refreshSets = async () => {
      try {
        const latestSets = await fetchJson<FlashcardSet[]>("/api/proxy/api/flashcard-sets");
        if (!cancelled) {
          setSets(latestSets);
          setListError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setListError(getErrorMessage(error, "Unable to refresh flashcard sets."));
        }
      }
    };

    void refreshSets();
    const intervalId = window.setInterval(() => {
      void refreshSets();
    }, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [hasProcessingSets]);

  async function createSet() {
    setCreatingManual(true);
    setManualError(null);
    try {
      const created = await fetchJson<FlashcardSet>("/api/proxy/api/flashcard-sets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: manualForm.name,
          description: manualForm.description,
          tags: parseTags(manualForm.tags),
        }),
      });
      setSets((current) => [created, ...current]);
      setManualForm({
        name: "",
        description: "",
        tags: "",
      });
      setView("sets");
      router.replace("/flashcards?view=sets");
    } catch (requestError) {
      setManualError(getErrorMessage(requestError, "Unable to create the flashcard set."));
    } finally {
      setCreatingManual(false);
    }
  }

  async function importSet() {
    setCreatingImport(true);
    setImportError(null);
    try {
      const created = await fetchJson<FlashcardSet>("/api/proxy/api/flashcard-sets/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(importForm),
      });
      setSets((current) => [created, ...current]);
      setImportForm({
        name: "",
        description: "",
        source_text: "",
      });
      setView("sets");
      router.replace("/flashcards?view=sets");
    } catch (requestError) {
      setImportError(getErrorMessage(requestError, "Unable to import the flashcard set."));
    } finally {
      setCreatingImport(false);
    }
  }

  async function deleteSet(id: string) {
    setDeletingSetId(id);
    setListError(null);
    try {
      await fetchVoid(`/api/proxy/api/flashcard-sets/${id}`, {
        method: "DELETE",
      });
      setSets((current) => current.filter((item) => item.id !== id));
    } catch (requestError) {
      setListError(getErrorMessage(requestError, "Unable to delete the flashcard set."));
    } finally {
      setDeletingSetId(null);
    }
  }

  return (
    <div className={view === "create" ? "stack" : "grid"}>
      {view === "create" ? (
      <section className="panel">
        <h2>Create Flashcard Set</h2>
        <div className="form-grid">
          <label>
            Name
            <input
              value={manualForm.name}
              onChange={(event) => setManualForm({ ...manualForm, name: event.target.value })}
            />
          </label>
          <label>
            Description
            <textarea
              value={manualForm.description}
              onChange={(event) =>
                setManualForm({ ...manualForm, description: event.target.value })
              }
              rows={3}
            />
          </label>
          <label>
            Tags
            <input
              value={manualForm.tags}
              onChange={(event) => setManualForm({ ...manualForm, tags: event.target.value })}
              placeholder="lesson-1, travel, nouns"
            />
          </label>
          <button
            className="primary-button"
            onClick={createSet}
            disabled={creatingManual || !manualForm.name.trim()}
          >
            {creatingManual ? "Creating..." : "Create Set"}
          </button>
          {manualError ? <InlineMessage>{manualError}</InlineMessage> : null}
        </div>
      </section>
      ) : null}

      {view === "create" ? (
      <section className="panel">
        <h2>Import With AI</h2>
        <div className="form-grid">
          <label>
            Set Name
            <input
              value={importForm.name}
              onChange={(event) => setImportForm({ ...importForm, name: event.target.value })}
            />
          </label>
          <label>
            Optional Description
            <textarea
              value={importForm.description}
              onChange={(event) =>
                setImportForm({ ...importForm, description: event.target.value })
              }
              rows={3}
            />
          </label>
          <label>
            Word List
            <textarea
              value={importForm.source_text}
              onChange={(event) =>
                setImportForm({ ...importForm, source_text: event.target.value })
              }
              rows={8}
              placeholder={"공항 - airport\n호텔 - hotel\n여권 - passport"}
            />
          </label>
          <p className="subtle">
            One flashcard per line. Supported separators, in order: tab, <code> - </code>,
            <code> : </code>, and <code> = </code>.
          </p>
          <button
            className="primary-button"
            onClick={importSet}
            disabled={creatingImport || !importForm.name.trim() || !importForm.source_text.trim()}
          >
            {creatingImport ? "Processing..." : "Import With AI"}
          </button>
          {importError ? <InlineMessage>{importError}</InlineMessage> : null}
        </div>
      </section>
      ) : null}

      {view === "sets" ? (
      <section className="panel full-span">
        <div className="row-between">
          <h2>Your Sets</h2>
          {hasProcessingSets ? (
            <p className="subtle">Imported sets refresh automatically while processing.</p>
          ) : null}
        </div>
        {listError ? <MessageBanner>{listError}</MessageBanner> : null}
        <div className="stack">
          {sets.map((set) => (
            <article className="card" key={set.id}>
              <div className="row-between">
                <div>
                  <h3>{set.name}</h3>
                  <p className="subtle">{set.description || "No description"}</p>
                  <p className="subtle">
                    {set.source === "ai_list" ? "AI import" : "Manual set"} · {set.status}
                  </p>
                </div>
                <span className={`status-pill ${set.status}`}>{set.status}</span>
              </div>
              <p className="tag-row">{set.tags.map((tag) => `#${tag}`).join(" ") || "No tags yet"}</p>
              {set.status === "processing" ? (
                <p className="subtle">
                  AI is enriching this set with tags, difficulty, notes, and examples.
                </p>
              ) : null}
              {set.generation_error ? <p className="error-text">{set.generation_error}</p> : null}
              <div className="button-row">
                <Link className="ghost-button" href={`/flashcards/${set.id}`}>
                  {set.status === "processing" || set.status === "failed" ? "Open Set" : "Manage Cards"}
                </Link>
                {set.status === "active" || set.status === "done" ? (
                  <Link className="ghost-button" href={`/flashcards/${set.id}/study`}>
                    Study
                  </Link>
                ) : null}
                <button
                  className="danger-button"
                  disabled={deletingSetId === set.id}
                  onClick={() => deleteSet(set.id)}
                >
                  {deletingSetId === set.id ? "Deleting..." : "Delete"}
                </button>
              </div>
            </article>
          ))}
          {sets.length === 0 ? <p className="subtle">Create your first set to start building a deck.</p> : null}
        </div>
      </section>
      ) : null}
    </div>
  );
}
