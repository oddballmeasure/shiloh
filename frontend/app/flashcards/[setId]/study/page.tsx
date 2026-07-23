import { notFound } from "next/navigation";

import { StudySessionView } from "@/components/study-session";
import { backendFetch, requireSession } from "@/lib/server-api";
import type { FlashcardSet, StudySession } from "@/lib/types";

export default async function StudyPage({
  params,
}: {
  params: Promise<{ setId: string }>;
}) {
  const { setId } = await params;
  const session = await requireSession();
  let flashcardSet: FlashcardSet;
  try {
    flashcardSet = await backendFetch<FlashcardSet>(
      `/api/flashcard-sets/${setId}`,
      {},
      session.backendToken,
    );
  } catch {
    notFound();
  }
  if (flashcardSet.status !== "active" && flashcardSet.status !== "done") {
    return (
      <section className="panel">
        <div className="stack">
          <h1>{flashcardSet.name}</h1>
          <p className="subtle">
            This set is currently {flashcardSet.status} and cannot be studied yet.
          </p>
          {flashcardSet.generation_error ? (
            <p className="error-text">{flashcardSet.generation_error}</p>
          ) : null}
        </div>
      </section>
    );
  }
  const studySession = await backendFetch<StudySession>(
    `/api/flashcard-sets/${setId}/study-session`,
    {
      method: "POST",
      body: JSON.stringify({ limit: 20 }),
    },
    session.backendToken,
  );
  return <StudySessionView flashcardSet={flashcardSet} initialSession={studySession} />;
}
