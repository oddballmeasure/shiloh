import fs from "node:fs/promises";

import { encode } from "@auth/core/jwt";
import { expect, test } from "@playwright/test";

import { ADMIN_STATE_PATH, AUTH_DIRECTORY, LEARNER_STATE_PATH } from "./auth-files";

type SyncedUser = {
  access_token: string;
  user: {
    id: string;
    role: "learner" | "admin" | "super_admin";
    status: "active" | "deactivated";
    discord_id: string;
  };
};

async function syncUser(discordId: string, username: string): Promise<SyncedUser> {
  const response = await fetch("http://127.0.0.1:8100/internal/auth/sync", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-internal-auth-secret": "internal-secret-with-at-least-thirty-two-bytes",
    },
    body: JSON.stringify({
      discord_id: discordId,
      email: `${discordId}@example.com`,
      username,
      avatar_url: `https://cdn.example.com/${discordId}.png`,
      discord_profile_snapshot: {
        id: discordId,
        username,
        email: `${discordId}@example.com`,
        locale: "en-US",
      },
    }),
  });
  expect(response.ok).toBeTruthy();
  return (await response.json()) as SyncedUser;
}

async function createStorageState(path: string, payload: SyncedUser) {
  const sessionToken = await encode({
    secret: process.env.AUTH_SECRET!,
    salt: "authjs.session-token",
    token: {
      sub: payload.user.id,
      userId: payload.user.id,
      role: payload.user.role,
      status: payload.user.status,
      discordId: payload.user.discord_id,
      backendToken: payload.access_token,
      name: payload.user.discord_id,
    },
  });

  const expiresAt = Math.floor(Date.now() / 1000) + 7 * 24 * 60 * 60;
  await fs.writeFile(
    path,
    JSON.stringify(
      {
        cookies: [
          {
            name: "authjs.session-token",
            value: sessionToken,
            domain: "127.0.0.1",
            path: "/",
            expires: expiresAt,
            httpOnly: true,
            secure: false,
            sameSite: "Lax",
          },
        ],
        origins: [],
      },
      null,
      2,
    ),
  );
}

async function createLearnerContent(accessToken: string) {
  const authHeaders = {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
  };

  const setResponse = await fetch("http://127.0.0.1:8100/api/flashcard-sets", {
    method: "POST",
    headers: authHeaders,
    body: JSON.stringify({
      name: "Seeded Travel Set",
      description: "Seed data for the admin view.",
      tags: ["travel", "seeded"],
    }),
  });
  expect(setResponse.ok).toBeTruthy();
  const flashcardSet = await setResponse.json();

  const cardResponse = await fetch(
    `http://127.0.0.1:8100/api/flashcard-sets/${flashcardSet.id}/flashcards`,
    {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        korean: "공항",
        english: "airport",
        difficulty: "hard",
        notes: "Seed card",
        tags: ["travel"],
      }),
    },
  );
  expect(cardResponse.ok).toBeTruthy();

  const manualAssignment = await fetch("http://127.0.0.1:8100/api/assignments", {
    method: "POST",
    headers: authHeaders,
    body: JSON.stringify({
      title: "Seeded Manual Assignment",
      instructions: "Choose the correct answer.",
      target_level: "beginner",
      questions: [
        {
          type: "multiple_choice",
          prompt: "Choose hello in Korean.",
          options: ["안녕하세요", "학교"],
          correct_answer: "안녕하세요",
          accepted_answers: ["안녕하세요"],
        },
      ],
    }),
  });
  expect(manualAssignment.ok).toBeTruthy();

  const pdfForm = new FormData();
  pdfForm.append("title", "Seeded PDF Assignment");
  pdfForm.append("target_level", "beginner");
  pdfForm.append("study_context", "Seed notes");
  pdfForm.append(
    "file",
    new File(["%PDF-1.4 seeded"], "seeded.pdf", { type: "application/pdf" }),
  );

  const pdfAssignment = await fetch("http://127.0.0.1:8100/api/assignments/generate-from-pdf", {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: pdfForm,
  });
  expect(pdfAssignment.ok).toBeTruthy();
}

test("seed learner and admin auth states", async () => {
  await fs.mkdir(AUTH_DIRECTORY, { recursive: true });

  const reset = await fetch("http://127.0.0.1:8100/internal/test/reset", { method: "POST" });
  expect(reset.ok).toBeTruthy();

  const learner = await syncUser("discord-learner", "Learner");
  const initialAdmin = await syncUser("discord-admin", "Administrator");
  const promoteResponse = await fetch("http://127.0.0.1:8100/internal/test/users/discord-admin/role", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role: "super_admin" }),
  });
  expect(promoteResponse.ok).toBeTruthy();
  const admin = await syncUser("discord-admin", "Administrator");

  await createLearnerContent(learner.access_token);
  await createStorageState(LEARNER_STATE_PATH, learner);
  await createStorageState(ADMIN_STATE_PATH, admin);
  expect(initialAdmin.user.role).toBe("learner");
  expect(admin.user.role).toBe("super_admin");
});
