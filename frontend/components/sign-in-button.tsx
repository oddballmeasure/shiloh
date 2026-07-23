"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";

export function SignInButton() {
  const [pending, setPending] = useState(false);

  return (
    <button
      className="primary-button"
      disabled={pending}
      onClick={() => {
        setPending(true);
        void signIn("discord", { callbackUrl: "/dashboard" });
      }}
    >
      {pending ? "Redirecting..." : "Continue With Discord"}
    </button>
  );
}
