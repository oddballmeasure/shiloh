"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Session } from "next-auth";

import { SignOutButton } from "@/components/sign-out-button";

export function Nav({ session }: { session: Session | null }) {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [flashcardMenuOpen, setFlashcardMenuOpen] = useState(false);
  const [assignmentMenuOpen, setAssignmentMenuOpen] = useState(false);

  useEffect(() => {
    setMobileMenuOpen(false);
    setFlashcardMenuOpen(false);
    setAssignmentMenuOpen(false);
  }, [pathname]);
  const canAdminister = session?.user.role !== "learner";

  const navItems = session
    ? [
        { href: "/dashboard", label: "Dashboard" },
        { href: "/profile", label: "Profile" },
        ...(canAdminister ? [{ href: "/admin", label: "Admin" }] : []),
      ]
    : [{ href: "/", label: "Home" }];

  return (
    <header className="topbar">
      <div>
        <Link className="brand" href={session ? "/dashboard" : "/"}>
          Shiloh Korean Study
        </Link>
        <p className="subtle">Discord-authenticated learner workspace with AI-backed assignments.</p>
      </div>
      <nav className="nav-links nav-links-desktop">
        {navItems.map((item) => (
          <Link key={item.href} href={item.href}>
            {item.label}
          </Link>
        ))}
        {session ? (
          <div className="nav-dropdown">
            <button
              aria-expanded={flashcardMenuOpen}
              className="ghost-button nav-dropdown-trigger"
              onClick={() => setFlashcardMenuOpen((current) => !current)}
              type="button"
            >
              Flashcards
            </button>
            {flashcardMenuOpen ? (
              <div className="nav-dropdown-menu">
                <Link className="nav-dropdown-link" href="/flashcards?view=sets">
                  View Sets
                </Link>
                <Link className="nav-dropdown-link" href="/flashcards?view=create">
                  Create Set
                </Link>
              </div>
            ) : null}
          </div>
        ) : null}
        {session ? (
          <div className="nav-dropdown">
            <button
              aria-expanded={assignmentMenuOpen}
              className="ghost-button nav-dropdown-trigger"
              onClick={() => setAssignmentMenuOpen((current) => !current)}
              type="button"
            >
              Assignments
            </button>
            {assignmentMenuOpen ? (
              <div className="nav-dropdown-menu">
                <Link className="nav-dropdown-link" href="/assignments?view=available">
                  View Available
                </Link>
                <Link className="nav-dropdown-link" href="/assignments?view=create">
                  Create Assignment
                </Link>
              </div>
            ) : null}
          </div>
        ) : null}
        {session ? <SignOutButton /> : null}
      </nav>
      {session ? (
        <div className="nav-mobile-shell">
          <button
            aria-controls="mobile-navigation"
            aria-expanded={mobileMenuOpen}
            aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            className="nav-toggle ghost-button"
            onClick={() => setMobileMenuOpen((current) => !current)}
            type="button"
          >
            {mobileMenuOpen ? "Close" : "Menu"}
          </button>
          {mobileMenuOpen ? (
            <div className="nav-drawer" id="mobile-navigation">
              {navItems.map((item) => (
                <Link key={item.href} className="nav-drawer-link" href={item.href}>
                  {item.label}
                </Link>
              ))}
              <div className="nav-drawer-group">
                <p className="subtle">Flashcards</p>
                <Link className="nav-drawer-link" href="/flashcards?view=sets">
                  View Sets
                </Link>
                <Link className="nav-drawer-link" href="/flashcards?view=create">
                  Create Set
                </Link>
              </div>
              <div className="nav-drawer-group">
                <p className="subtle">Assignments</p>
                <Link className="nav-drawer-link" href="/assignments?view=available">
                  View Available
                </Link>
                <Link className="nav-drawer-link" href="/assignments?view=create">
                  Create Assignment
                </Link>
              </div>
              <SignOutButton />
            </div>
          ) : null}
        </div>
      ) : null}
    </header>
  );
}
