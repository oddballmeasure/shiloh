import { AdminNav } from "@/components/admin-nav";
import { DeleteResourceButton } from "@/components/delete-resource-button";
import { backendFetch, requireAdminSession } from "@/lib/server-api";
import type { Assignment } from "@/lib/types";

export default async function AdminAssignmentsPage() {
  const session = await requireAdminSession();
  const assignments = await backendFetch<Assignment[]>("/api/admin/assignments", {}, session.backendToken);

  return (
    <section className="panel">
      <h1>Assignment Moderation</h1>
      <AdminNav />
      <div className="stack">
        {assignments.map((assignment) => (
          <article className="card" key={assignment.id}>
            <div className="row-between">
              <div>
                <h3>{assignment.title}</h3>
                <p className="subtle">
                  {assignment.owner_id} · {assignment.source} · {assignment.status}
                </p>
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
              </div>
              <DeleteResourceButton
                path={`/api/proxy/api/admin/assignments/${assignment.id}`}
                label="Delete Assignment"
              />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
