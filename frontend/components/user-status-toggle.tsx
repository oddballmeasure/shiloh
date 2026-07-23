"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { InlineMessage } from "@/components/inline-message";
import { fetchVoid, getErrorMessage } from "@/lib/client-api";

export function UserStatusToggle({
  userId,
  active,
}: {
  userId: string;
  active: boolean;
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  return (
    <div className="stack">
      <button
        className={active ? "danger-button" : "primary-button"}
        disabled={pending}
        onClick={async () => {
          setPending(true);
          setError(null);
          try {
            await fetchVoid(
              `/api/proxy/api/admin/users/${userId}/${active ? "deactivate" : "reactivate"}`,
              {
                method: "POST",
              },
            );
            router.refresh();
          } catch (requestError) {
            setError(getErrorMessage(requestError, "Unable to update the user status."));
          } finally {
            setPending(false);
          }
        }}
      >
        {pending ? "Saving..." : active ? "Deactivate User" : "Reactivate User"}
      </button>
      {error ? <InlineMessage>{error}</InlineMessage> : null}
    </div>
  );
}
