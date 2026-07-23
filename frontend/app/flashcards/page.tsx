import { FlashcardSetManager } from "@/components/flashcard-set-manager";
import { backendFetch, requireSession } from "@/lib/server-api";
import type { FlashcardSet } from "@/lib/types";

export default async function FlashcardsPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await requireSession();
  const params = (await searchParams) ?? {};
  const initialView = params.view === "create" ? "create" : "sets";
  const sets = await backendFetch<FlashcardSet[]>("/api/flashcard-sets", {}, session.backendToken);

  return <FlashcardSetManager initialSets={sets} initialView={initialView} />;
}
