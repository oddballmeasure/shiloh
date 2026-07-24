import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { env } from "@/lib/env";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function collectMessages(value: unknown): string[] {
  if (typeof value === "string") {
    return value.trim() ? [value.trim()] : [];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item) => collectMessages(item));
  }
  if (value && typeof value === "object") {
    const payload = value as Record<string, unknown>;
    if (typeof payload.msg === "string" && payload.msg.trim()) {
      return [payload.msg.trim()];
    }
    if (typeof payload.message === "string" && payload.message.trim()) {
      return [payload.message.trim()];
    }
    if ("detail" in payload) {
      return collectMessages(payload.detail);
    }
    if ("errors" in payload) {
      return collectMessages(payload.errors);
    }
  }
  return [];
}

async function readApiError(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      const payload = (await response.json()) as unknown;
      const messages = collectMessages(payload);
      if (messages.length > 0) {
        return messages.join(" ");
      }
    } catch {
      // Fall through to text parsing.
    }
  }

  try {
    const detail = await response.text();
    if (detail.trim()) {
      return detail.trim();
    }
  } catch {
    // Ignore body read failures and use the fallback below.
  }

  return response.statusText || "Backend request failed.";
}

export async function requireSession() {
  const session = await auth();
  if (!session?.backendToken || !session.user?.id) {
    redirect("/");
  }
  if (session.user.status === "deactivated") {
    redirect("/?error=AccountDeactivated");
  }
  try {
    await backendFetch("/api/profile", {}, session.backendToken);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect("/?error=SessionExpired");
    }
    if (error instanceof ApiError && error.status === 403) {
      redirect("/?error=AccountDeactivated");
    }
    throw error;
  }
  return session;
}

export async function requireAdminSession() {
  const session = await requireSession();
  if (!["admin", "super_admin"].includes(session.user.role)) {
    redirect("/dashboard");
  }
  return session;
}

export async function backendFetch<T>(
  path: string,
  options: RequestInit = {},
  backendToken?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (backendToken) {
    headers.set("Authorization", `Bearer ${backendToken}`);
  }
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${env.backendUrl}${path}`, {
      ...options,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Unable to reach the backend service. Please try again shortly.", 503);
  }

  if (!response.ok) {
    throw new ApiError(await readApiError(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
