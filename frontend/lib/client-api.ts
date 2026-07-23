export class ClientRequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function collectErrorMessages(value: unknown): string[] {
  if (typeof value === "string") {
    return value.trim() ? [value.trim()] : [];
  }

  if (Array.isArray(value)) {
    return value.flatMap((item) => collectErrorMessages(item));
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
      return collectErrorMessages(payload.detail);
    }
    if ("errors" in payload) {
      return collectErrorMessages(payload.errors);
    }
  }

  return [];
}

async function readErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      const payload = (await response.json()) as unknown;
      const messages = collectErrorMessages(payload);
      if (messages.length > 0) {
        return messages.join(" ");
      }
    } catch {
      // Fall through to text parsing.
    }
  }

  try {
    const text = (await response.text()).trim();
    if (text) {
      return text;
    }
  } catch {
    // Ignore body read errors and use the generic fallback below.
  }

  return response.statusText || `Request failed with status ${response.status}.`;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new ClientRequestError(await readErrorMessage(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return undefined as T;
}

export async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  try {
    return await handleResponse<T>(await fetch(input, init));
  } catch (error) {
    if (error instanceof ClientRequestError) {
      throw error;
    }
    throw new ClientRequestError(
      "Unable to reach the server. Check your connection and try again.",
      0,
    );
  }
}

export async function fetchVoid(input: RequestInfo | URL, init?: RequestInit): Promise<void> {
  await fetchJson<void>(input, init);
}

export function getErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (error instanceof ClientRequestError) {
    return error.message;
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
}
