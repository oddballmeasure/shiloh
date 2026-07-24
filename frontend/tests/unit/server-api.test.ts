import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

vi.mock("@/auth", () => ({
  auth: vi.fn(),
}));

import { auth } from "@/auth";
import { backendFetch, requireSession } from "@/lib/server-api";
import { redirect } from "next/navigation";

describe("server-api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("adds authorization and json headers for backend requests", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(Response.json({ status: "ok" }, { status: 200 }));

    await expect(
      backendFetch<{ status: string }>(
        "/api/profile",
        {
          method: "POST",
          body: JSON.stringify({ ping: true }),
        },
        "backend-token",
      ),
    ).resolves.toEqual({ status: "ok" });

    const [requestUrl, init] = fetchMock.mock.calls[0];
    expect(requestUrl).toBe("http://127.0.0.1:8100/api/profile");
    expect(init?.headers).toBeInstanceOf(Headers);
    const headers = init?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer backend-token");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("returns a readable backend error payload", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      Response.json(
        {
          detail: [{ msg: "Manual assignments require at least one question." }],
        },
        { status: 422 },
      ),
    );

    await expect(backendFetch("/api/assignments")).rejects.toMatchObject({
      message: "Manual assignments require at least one question.",
      status: 422,
    });
  });

  it("returns a controlled message when the backend is unreachable", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockRejectedValue(new Error("connect ECONNREFUSED"));

    await expect(backendFetch("/api/assignments")).rejects.toMatchObject({
      message: "Unable to reach the backend service. Please try again shortly.",
      status: 503,
    });
  });

  it("redirects stale backend sessions to a readable sign-in state", async () => {
    vi.mocked(redirect).mockImplementation(() => {
      throw new Error("redirect");
    });
    vi.mocked(auth).mockResolvedValue({
      backendToken: "stale-token",
      user: {
        id: "missing-user",
        role: "learner",
        status: "active",
        discordId: "discord-user",
      },
      expires: "2099-01-01T00:00:00.000Z",
    });
    vi.mocked(fetch).mockResolvedValue(
      Response.json({ detail: "Authenticated user not found." }, { status: 401 }),
    );

    await expect(requireSession()).rejects.toThrow("redirect");

    expect(redirect).toHaveBeenCalledWith("/?error=SessionExpired");
  });
});
