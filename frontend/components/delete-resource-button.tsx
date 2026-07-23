"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { InlineMessage } from "@/components/inline-message";
import { fetchVoid, getErrorMessage } from "@/lib/client-api";

export function DeleteResourceButton({
  path,
  label,
}: {
  path: string;
  label: string;
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  return (
    <div className="stack">
      <button
        className="danger-button"
        disabled={pending}
        onClick={async () => {
          setPending(true);
          setError(null);
          try {
            await fetchVoid(path, { method: "DELETE" });
            router.refresh();
          } catch (requestError) {
            setError(getErrorMessage(requestError, `Unable to ${label.toLowerCase()}.`));
          } finally {
            setPending(false);
          }
        }}
      >
        {pending ? "Deleting..." : label}
      </button>
      {error ? <InlineMessage>{error}</InlineMessage> : null}
    </div>
  );
}
