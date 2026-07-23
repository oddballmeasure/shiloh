import { AdminNav } from "@/components/admin-nav";
import { UserRoleToggle } from "@/components/user-role-toggle";
import { UserStatusToggle } from "@/components/user-status-toggle";
import { backendFetch, requireAdminSession } from "@/lib/server-api";
import type { AdminUserDetail } from "@/lib/types";

export default async function AdminUserDetailPage({
  params,
}: {
  params: Promise<{ userId: string }>;
}) {
  const { userId } = await params;
  const session = await requireAdminSession();
  const detail = await backendFetch<AdminUserDetail>(
    `/api/admin/users/${userId}`,
    {},
    session.backendToken,
  );

  return (
    <div className="stack">
      <section className="panel">
        <div className="row-between">
          <div>
            <h1>{detail.user.username}</h1>
            <p className="subtle">
              {detail.user.role} · {detail.user.status}
            </p>
            <p className="subtle">Email: {detail.user.email || "Not available"}</p>
            <p className="subtle">Discord ID: {detail.user.discord_id}</p>
          </div>
          <div className="button-row">
            <UserStatusToggle userId={detail.user.id} active={detail.user.status === "active"} />
            {session.user.role === "super_admin" ? (
              <UserRoleToggle userId={detail.user.id} role={detail.user.role} />
            ) : null}
          </div>
        </div>
        <AdminNav />
      </section>

      <section className="panel">
        <h2>Current Discord Profile</h2>
        <pre className="json-block">
          {JSON.stringify(detail.user.discord_profile_snapshot ?? {}, null, 2)}
        </pre>
      </section>

      <section className="panel">
        <h2>Flashcard Sets</h2>
        <div className="stack">
          {detail.flashcard_sets.map((flashcardSet) => (
            <article className="card" key={flashcardSet.id}>
              <div className="row-between">
                <h3>{flashcardSet.name}</h3>
                <span className={`status-pill ${flashcardSet.status}`}>{flashcardSet.status}</span>
              </div>
              <p className="subtle">{flashcardSet.source}</p>
              <p className="tag-row">{flashcardSet.tags.join(", ") || "No tags yet"}</p>
              {flashcardSet.generation_error ? (
                <p className="error-text">{flashcardSet.generation_error}</p>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Flashcards</h2>
        <div className="stack">
          {detail.flashcards.map((flashcard) => (
            <article className="card" key={flashcard.id}>
              <div className="row-between">
                <h3>{flashcard.korean}</h3>
                <span className={`status-pill ${flashcard.difficulty}`}>{flashcard.difficulty}</span>
              </div>
              <p className="subtle">{flashcard.english}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Assignments</h2>
        <div className="stack">
          {detail.assignments.map((assignment) => (
            <article className="card" key={assignment.id}>
              <div className="row-between">
                <h3>{assignment.title}</h3>
                <span className={`status-pill ${assignment.status}`}>{assignment.status}</span>
              </div>
              <p className="subtle">{assignment.source}</p>
              {assignment.generation_error ? (
                <p className="error-text">{assignment.generation_error}</p>
              ) : null}
              {assignment.source_file ? (
                <p>
                  <a
                    className="ghost-button"
                    href={`/api/proxy/api/admin/assignments/${assignment.id}/source-file`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View Submitted PDF
                  </a>
                </p>
              ) : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
