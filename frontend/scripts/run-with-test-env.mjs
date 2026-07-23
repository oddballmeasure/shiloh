import { spawn } from "node:child_process";

const [command, ...args] = process.argv.slice(2);

if (!command) {
  console.error("Usage: node scripts/run-with-test-env.mjs <command> [...args]");
  process.exit(1);
}

const env = {
  AUTH_SECRET: "test-auth-secret-with-at-least-thirty-two-bytes",
  AUTH_DISCORD_ID: "test-discord-client-id",
  AUTH_DISCORD_SECRET: "test-discord-client-secret",
  BACKEND_URL: "http://127.0.0.1:8100",
  BACKEND_INTERNAL_AUTH_SECRET: "internal-secret-with-at-least-thirty-two-bytes",
  NEXTAUTH_URL: "http://127.0.0.1:3100",
  ...process.env,
};

const child = spawn(command, args, {
  env,
  stdio: "inherit",
  shell: process.platform === "win32",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
