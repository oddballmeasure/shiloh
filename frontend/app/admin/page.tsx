import { AdminNav } from "@/components/admin-nav";
import { backendFetch, requireAdminSession } from "@/lib/server-api";
import type { Assignment, FlashcardSet, User } from "@/lib/types";

export default async function AdminHomePage() {
  const session = await requireAdminSession();
  const [users, flashcardSets, assignments] = await Promise.all([
    backendFetch<User[]>("/api/admin/users", {}, session.backendToken),
    backendFetch<FlashcardSet[]>("/api/admin/flashcard-sets", {}, session.backendToken),
    backendFetch<Assignment[]>("/api/admin/assignments", {}, session.backendToken),
  ]);

  const activeUsers = users.filter((user) => user.status === "active").length;

  return (
    <div className="stack">
      <section className="panel">
        <div className="row-between">
          <div>
            <h1>Admin Panel</h1>
            <p className="subtle">
              Review learners, moderate study content, and manage platform access.
            </p>
          </div>
          <span className="status-pill active">{session.user.role.replace("_", " ")}</span>
        </div>
        <AdminNav />
      </section>

      <section className="stats-grid">
        <article className="metric-card">
          <span>Total Users</span>
          <strong>{users.length}</strong>
        </article>
        <article className="metric-card">
          <span>Active Users</span>
          <strong>{activeUsers}</strong>
        </article>
        <article className="metric-card">
          <span>Flashcard Sets</span>
          <strong>{flashcardSets.length}</strong>
        </article>
        <article className="metric-card">
          <span>Assignments</span>
          <strong>{assignments.length}</strong>
        </article>
      </section>
    </div>
  );
}
