import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { authMock } = vi.hoisted(() => ({
  authMock: vi.fn(),
}));

vi.mock("@/auth", () => ({
  auth: authMock,
}));

import { GET, POST } from "@/app/api/proxy/[...path]/route";

describe("proxy route", () => {
  beforeEach(() => {
    authMock.mockReset();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("returns 401 when no session is present", async () => {
    authMock.mockResolvedValue(null);

    const response = await GET(
      new NextRequest("http://127.0.0.1:3100/api/proxy/api/profile"),
      { params: Promise.resolve({ path: ["api", "profile"] }) },
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ detail: "Unauthorized" });
  });

  it("returns 503 when the backend fetch fails", async () => {
    authMock.mockResolvedValue({ backendToken: "backend-token" });
    vi.mocked(fetch).mockRejectedValue(new Error("connect ECONNREFUSED"));

    const response = await GET(
      new NextRequest("http://127.0.0.1:3100/api/proxy/api/profile"),
      { params: Promise.resolve({ path: ["api", "profile"] }) },
    );

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      detail: "Unable to reach the backend service. Please try again shortly.",
    });
  });

  it("passes through validation errors from the backend", async () => {
    authMock.mockResolvedValue({ backendToken: "backend-token" });
    vi.mocked(fetch).mockResolvedValue(
      Response.json(
        { detail: [{ msg: "String should have at least 1 character" }] },
        { status: 422 },
      ),
    );

    const response = await POST(
      new NextRequest("http://127.0.0.1:3100/api/proxy/api/assignments", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title: "" }),
      }),
      { params: Promise.resolve({ path: ["api", "assignments"] }) },
    );

    expect(response.status).toBe(422);
    await expect(response.json()).resolves.toEqual({
      detail: [{ msg: "String should have at least 1 character" }],
    });
  });

  it("preserves file response headers", async () => {
    authMock.mockResolvedValue({ backendToken: "backend-token" });
    vi.mocked(fetch).mockResolvedValue(
      new Response("pdf-content", {
        status: 200,
        headers: {
          "content-type": "application/pdf",
          "content-disposition": 'inline; filename="lesson.pdf"',
        },
      }),
    );

    const response = await GET(
      new NextRequest("http://127.0.0.1:3100/api/proxy/api/assignments/file"),
      { params: Promise.resolve({ path: ["api", "assignments", "file"] }) },
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("application/pdf");
    expect(response.headers.get("content-disposition")).toBe('inline; filename="lesson.pdf"');
    await expect(response.text()).resolves.toBe("pdf-content");
  });

  it("forwards multipart uploads without stripping the file payload", async () => {
    authMock.mockResolvedValue({ backendToken: "backend-token" });
    vi.mocked(fetch).mockResolvedValue(Response.json({ id: "assignment-1" }, { status: 201 }));

    const formData = new FormData();
    formData.append("title", "Lesson PDF");
    formData.append("target_level", "beginner");
    formData.append("file", new File(["%PDF-1.4"], "lesson.pdf", { type: "application/pdf" }));

    const response = await POST(
      new NextRequest("http://127.0.0.1:3100/api/proxy/api/assignments/generate-from-pdf", {
        method: "POST",
        body: formData,
      }),
      {
        params: Promise.resolve({
          path: ["api", "assignments", "generate-from-pdf"],
        }),
      },
    );

    expect(response.status).toBe(201);
    const [requestUrl, init] = vi.mocked(fetch).mock.calls[0];
    expect(requestUrl).toBe("http://127.0.0.1:8100/api/assignments/generate-from-pdf");
    const headers = init?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer backend-token");
    expect(headers.get("Content-Type")).toContain("multipart/form-data; boundary=");
    expect(Buffer.isBuffer(init?.body)).toBe(true);
    expect((init?.body as Buffer).toString("utf8")).toContain("lesson.pdf");
  });
});
