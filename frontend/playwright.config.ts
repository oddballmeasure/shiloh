import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run --cache-dir /private/tmp/uv-cache uvicorn tests.e2e_backend:app --host 127.0.0.1 --port 8100",
      port: 8100,
      reuseExistingServer: true,
      cwd: "..",
      timeout: 60_000,
    },
    {
      command: "node ./scripts/run-with-test-env.mjs next dev --hostname 127.0.0.1 --port 3100",
      port: 3100,
      reuseExistingServer: true,
      cwd: ".",
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "chromium",
      testIgnore: /auth\.setup\.ts/,
      dependencies: ["setup"],
      use: {
        browserName: "chromium",
      },
    },
  ],
});
