import { afterEach, vi } from "vitest";

process.env.AUTH_SECRET ??= "test-auth-secret-with-at-least-thirty-two-bytes";
process.env.AUTH_DISCORD_ID ??= "test-discord-client-id";
process.env.AUTH_DISCORD_SECRET ??= "test-discord-client-secret";
process.env.BACKEND_URL ??= "http://127.0.0.1:8100";
process.env.BACKEND_INTERNAL_AUTH_SECRET ??= "internal-secret-with-at-least-thirty-two-bytes";
process.env.NEXTAUTH_URL ??= "http://127.0.0.1:3100";

afterEach(() => {
  vi.unstubAllGlobals();
});
