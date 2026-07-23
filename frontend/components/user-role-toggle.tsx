"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { InlineMessage } from "@/components/inline-message";
import { fetchVoid, getErrorMessage } from "@/lib/client-api";

export function UserRoleToggle({
  userId,
  role,
}: {
  userId: string;
  role: "learner" | "admin" | "super_admin";
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (role === "super_admin") {
    return null;
  }

  const nextAction = role === "admin" ? "demote-admin" : "promote-admin";
  const label = role === "admin" ? "Demote To Learner" : "Promote To Admin";

  return (
    <div className="stack">
      <button
        className="ghost-button"
        disabled={pending}
        onClick={async () => {
          setPending(true);
          setError(null);
          try {
            await fetchVoid(`/api/proxy/api/admin/users/${userId}/${nextAction}`, {
              method: "POST",
            });
            router.refresh();
          } catch (requestError) {
            setError(getErrorMessage(requestError, "Unable to update the user role."));
          } finally {
            setPending(false);
          }
        }}
      >
        {pending ? "Saving..." : label}
      </button>
      {error ? <InlineMessage>{error}</InlineMessage> : null}
    </div>
  );
}
