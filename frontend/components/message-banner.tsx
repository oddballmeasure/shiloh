import type { ReactNode } from "react";

export function MessageBanner({
  tone = "error",
  children,
}: {
  tone?: "error" | "info";
  children: ReactNode;
}) {
  return <div className={`message-banner ${tone}`}>{children}</div>;
}
