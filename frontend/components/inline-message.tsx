import type { ReactNode } from "react";

export function InlineMessage({
  tone = "error",
  children,
}: {
  tone?: "error" | "success" | "muted";
  children: ReactNode;
}) {
  return <p className={`inline-message ${tone}`}>{children}</p>;
}
