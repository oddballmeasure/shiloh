import Link from "next/link";

export function AdminNav() {
  return (
    <nav className="admin-nav">
      <Link className="ghost-button" href="/admin">
        Overview
      </Link>
      <Link className="ghost-button" href="/admin/users">
        Users
      </Link>
      <Link className="ghost-button" href="/admin/flashcard-sets">
        Flashcard Sets
      </Link>
      <Link className="ghost-button" href="/admin/assignments">
        Assignments
      </Link>
    </nav>
  );
}
