import Link from "next/link";

import { AdminNav } from "@/components/admin-nav";
import { backendFetch, requireAdminSession } from "@/lib/server-api";
import type { User } from "@/lib/types";

export default async function AdminUsersPage() {
  const session = await requireAdminSession();
  const users = await backendFetch<User[]>("/api/admin/users", {}, session.backendToken);

  return (
    <section className="panel">
      <h1>Users</h1>
      <AdminNav />
      <div className="stack">
        {users.map((user) => (
          <article className="card" key={user.id}>
            <div className="row-between">
              <div>
                <h3>{user.username}</h3>
                <p className="subtle">
                  {user.role} · {user.status}
                </p>
              </div>
              <Link className="ghost-button" href={`/admin/users/${user.id}`}>
                Inspect
              </Link>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
