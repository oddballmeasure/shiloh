import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { MessageBanner } from "@/components/message-banner";
import { SignInButton } from "@/components/sign-in-button";
import { SignOutButton } from "@/components/sign-out-button";
import { getAuthErrorMessage } from "@/lib/auth-errors";

export default async function HomePage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await auth();
  const params = (await searchParams) ?? {};
  const errorCode = typeof params.error === "string" ? params.error : null;
  const authError = getAuthErrorMessage(errorCode);
  const isDeactivated = session?.user?.status === "deactivated";
  const hasSessionError = errorCode === "SessionExpired";

  if (session?.backendToken && !isDeactivated && !hasSessionError) {
    redirect("/dashboard");
  }

  return (
    <div className="stack">
      {authError ? <MessageBanner>{authError}</MessageBanner> : null}
      <section className="hero panel">
        <div className="hero-copy">
          <p className="eyebrow">Korean Study Workspace</p>
          <h1>Flashcards, AI assignments, and admin controls in one learner app.</h1>
          <p className="subtle">
            Sign in with Discord to create weighted flashcard sets, generate Korean practice
            assignments, and track progress over time.
          </p>
          {isDeactivated ? (
            <div className="button-row">
              <SignOutButton />
            </div>
          ) : (
            <SignInButton />
          )}
        </div>
      </section>
    </div>
  );
}
