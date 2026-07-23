import { AdminNav } from "@/components/admin-nav";
import { DeleteResourceButton } from "@/components/delete-resource-button";
import { backendFetch, requireAdminSession } from "@/lib/server-api";
import type { FlashcardSet } from "@/lib/types";

export default async function AdminFlashcardSetsPage() {
  const session = await requireAdminSession();
  const sets = await backendFetch<FlashcardSet[]>("/api/admin/flashcard-sets", {}, session.backendToken);

  return (
    <section className="panel">
      <h1>Flashcard Set Moderation</h1>
      <AdminNav />
      <div className="stack">
        {sets.map((flashcardSet) => (
          <article className="card" key={flashcardSet.id}>
            <div className="row-between">
              <div>
                <h3>{flashcardSet.name}</h3>
                <p className="subtle">
                  {flashcardSet.owner_id} · {flashcardSet.source} · {flashcardSet.status}
                </p>
                {flashcardSet.generation_error ? (
                  <p className="error-text">{flashcardSet.generation_error}</p>
                ) : null}
              </div>
              <DeleteResourceButton
                path={`/api/proxy/api/admin/flashcard-sets/${flashcardSet.id}`}
                label="Delete Set"
              />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
