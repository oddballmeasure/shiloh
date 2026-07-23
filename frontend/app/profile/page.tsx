import { backendFetch, requireSession } from "@/lib/server-api";
import type { ProfileSummary } from "@/lib/types";

export default async function ProfilePage() {
  const session = await requireSession();
  const profile = await backendFetch<ProfileSummary>("/api/profile", {}, session.backendToken);

  return (
    <div className="stack">
      <section className="panel">
        <h1>{profile.user.username}</h1>
        <p className="subtle">Role: {profile.user.role}</p>
        <p className="subtle">Email: {profile.user.email || "Not available"}</p>
        <p className="subtle">Discord ID: {profile.user.discord_id}</p>
        {profile.user.last_login_at ? (
          <p className="subtle">Last Login: {new Date(profile.user.last_login_at).toLocaleString()}</p>
        ) : null}
      </section>

      <section className="stats-grid">
        <article className="metric-card">
          <span>Words Learned</span>
          <strong>{profile.words_learned}</strong>
        </article>
        <article className="metric-card">
          <span>Assignments Generated</span>
          <strong>{profile.assignments_generated}</strong>
        </article>
        <article className="metric-card">
          <span>Manual Assignments</span>
          <strong>{profile.assignments_manual}</strong>
        </article>
        <article className="metric-card">
          <span>Total Cards</span>
          <strong>{profile.flashcard_count}</strong>
        </article>
      </section>

      <section className="panel">
        <h2>Current Discord Profile</h2>
        <pre className="json-block">
          {JSON.stringify(profile.user.discord_profile_snapshot ?? {}, null, 2)}
        </pre>
      </section>
    </div>
  );
}
