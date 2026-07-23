"use client";

import { signOut } from "next-auth/react";

export function SignOutButton() {
  return (
    <button className="ghost-button" onClick={() => signOut({ callbackUrl: "/" })} type="button">
      Sign Out
    </button>
  );
}
