import Link from "next/link";

import { backendFetch, requireSession } from "@/lib/server-api";
import type { Assignment, FlashcardSet, ProfileSummary } from "@/lib/types";

export default async function DashboardPage() {
  const session = await requireSession();
  const canAdminister = session.user.role !== "learner";
  const [profile, sets, assignments] = await Promise.all([
    backendFetch<ProfileSummary>("/api/profile", {}, session.backendToken),
    backendFetch<FlashcardSet[]>("/api/flashcard-sets", {}, session.backendToken),
    backendFetch<Assignment[]>("/api/assignments", {}, session.backendToken),
  ]);

  return (
    <div className="stack">
      <section className="stats-grid">
        <article className="metric-card">
          <span>Words Learned</span>
          <strong>{profile.words_learned}</strong>
        </article>
        <article className="metric-card">
          <span>Assignments Completed</span>
          <strong>{profile.assignments_completed}</strong>
        </article>
        <article className="metric-card">
          <span>Flashcard Sets</span>
          <strong>{profile.flashcard_set_count}</strong>
        </article>
        <article className="metric-card">
          <span>Done Sets</span>
          <strong>{profile.done_set_count}</strong>
        </article>
      </section>

      <div className="grid">
        {canAdminister ? (
          <section className="panel full-span">
            <div className="row-between">
              <div>
                <h2>Admin Access</h2>
                <p className="subtle">
                  Open the moderation workspace for users, flashcard sets, and assignments.
                </p>
              </div>
              <Link className="primary-button" href="/admin">
                Open Admin Panel
              </Link>
            </div>
          </section>
        ) : null}

        <section className="panel">
          <div className="row-between">
            <h2>Recent Sets</h2>
            <Link className="ghost-button" href="/flashcards?view=sets">
              View All Sets
            </Link>
          </div>
          <div className="stack">
            {sets.slice(0, 5).map((set) => (
              <article className="card" key={set.id}>
                <div className="row-between">
                  <h3>{set.name}</h3>
                  <span className={`status-pill ${set.status}`}>{set.status}</span>
                </div>
                <p className="subtle">{set.description || "No description"}</p>
                <div className="button-row dashboard-card-actions">
                  <Link className="ghost-button" href={`/flashcards/${set.id}`}>
                    Open Set
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="row-between">
            <h2>Recent Assignments</h2>
            <div className="button-row dashboard-card-actions">
              <Link className="ghost-button" href="/assignments?view=available">
                Available
              </Link>
              <Link className="primary-button" href="/assignments?view=create">
                Create
              </Link>
            </div>
          </div>
          <div className="stack">
            {assignments.slice(0, 5).map((assignment) => (
              <article className="card" key={assignment.id}>
                <div className="row-between">
                  <h3>{assignment.title}</h3>
                  <span className={`status-pill ${assignment.status}`}>{assignment.status}</span>
                </div>
                <p className="subtle">
                  {assignment.source} · {assignment.target_level}
                </p>
                <div className="button-row dashboard-card-actions">
                  <Link className="ghost-button" href={`/assignments/${assignment.id}`}>
                    {assignment.status === "completed" ? "View Result" : "Open Assignment"}
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
