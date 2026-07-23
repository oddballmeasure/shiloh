import { describe, expect, it, vi } from "vitest";

import { ClientRequestError, fetchJson, getErrorMessage } from "@/lib/client-api";

describe("client-api", () => {
  it("extracts readable validation errors from JSON responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json(
          {
            detail: [
              { msg: "String should have at least 1 character" },
              { msg: "Multiple-choice questions require at least two options." },
            ],
          },
          { status: 422 },
        ),
      ),
    );

    await expect(fetchJson("/api/proxy/api/assignments")).rejects.toMatchObject({
      message:
        "String should have at least 1 character Multiple-choice questions require at least two options.",
      status: 422,
    });
  });

  it("falls back to a network error when fetch throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("socket hang up")));

    await expect(fetchJson("/api/proxy/api/assignments")).rejects.toEqual(
      new ClientRequestError("Unable to reach the server. Check your connection and try again.", 0),
    );
  });

  it("uses text bodies when the error is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("Backend temporarily unavailable.", {
          status: 503,
          headers: { "content-type": "text/plain" },
        }),
      ),
    );

    await expect(fetchJson("/api/proxy/api/assignments")).rejects.toMatchObject({
      message: "Backend temporarily unavailable.",
      status: 503,
    });
  });

  it("returns JSON payloads and normalizes helper messages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ ok: true }, { status: 200 })));

    await expect(fetchJson<{ ok: boolean }>("/api/proxy/health")).resolves.toEqual({ ok: true });
    expect(getErrorMessage(new Error("custom message"))).toBe("custom message");
  });
});
