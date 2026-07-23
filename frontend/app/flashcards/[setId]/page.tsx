import { notFound } from "next/navigation";

import { FlashcardSetDetail } from "@/components/flashcard-set-detail";
import { backendFetch, requireSession } from "@/lib/server-api";
import type { Flashcard, FlashcardSet } from "@/lib/types";

export default async function FlashcardSetPage({
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
  const flashcards =
    flashcardSet.status === "active" || flashcardSet.status === "done"
      ? await backendFetch<Flashcard[]>(
          `/api/flashcard-sets/${setId}/flashcards`,
          {},
          session.backendToken,
        )
      : [];
  return <FlashcardSetDetail initialSet={flashcardSet} initialFlashcards={flashcards} />;
}
