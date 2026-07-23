function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export const env = {
  authSecret: requireEnv("AUTH_SECRET"),
  discordClientId: requireEnv("AUTH_DISCORD_ID"),
  discordClientSecret: requireEnv("AUTH_DISCORD_SECRET"),
  backendUrl: requireEnv("BACKEND_URL").replace(/\/$/, ""),
  backendInternalAuthSecret: requireEnv("BACKEND_INTERNAL_AUTH_SECRET"),
};
