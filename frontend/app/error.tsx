"use client";

import { useEffect } from "react";

import { MessageBanner } from "@/components/message-banner";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="shell">
      <main className="content">
        <section className="panel error-panel">
          <h1>Something went wrong</h1>
          <MessageBanner>
            {error.message || "The application could not complete that request."}
          </MessageBanner>
          <button className="primary-button" onClick={() => reset()}>
            Try Again
          </button>
        </section>
      </main>
    </div>
  );
}
