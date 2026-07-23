import NextAuth from "next-auth";
import Discord from "next-auth/providers/discord";

import { env } from "@/lib/env";

function buildDiscordAvatar(discordId: string, avatar?: string | null): string | null {
  if (!avatar) {
    return null;
  }
  return `https://cdn.discordapp.com/avatars/${discordId}/${avatar}.png`;
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  secret: env.authSecret,
  trustHost: true,
  session: { strategy: "jwt" },
  providers: [
    Discord({
      clientId: env.discordClientId,
      clientSecret: env.discordClientSecret,
      authorization: {
        params: {
          scope: "identify email",
        },
      },
    }),
  ],
  pages: {
    signIn: "/",
    error: "/",
  },
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account?.provider === "discord" && profile) {
        const discordId = String(profile.id);
        const username =
          (typeof profile.global_name === "string" && profile.global_name) ||
          (typeof profile.username === "string" && profile.username) ||
          "Discord User";
        const avatarUrl = buildDiscordAvatar(
          discordId,
          typeof profile.avatar === "string" ? profile.avatar : null,
        );
        const email = typeof profile.email === "string" ? profile.email : null;
        const response = await fetch(`${env.backendUrl}/internal/auth/sync`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-internal-auth-secret": env.backendInternalAuthSecret,
          },
          body: JSON.stringify({
            discord_id: discordId,
            email,
            username,
            avatar_url: avatarUrl,
            discord_profile_snapshot: profile,
          }),
          cache: "no-store",
        });

        if (!response.ok) {
          let detail = "Failed to synchronize user with backend.";
          try {
            const payload = (await response.json()) as { detail?: string };
            detail = payload.detail || detail;
          } catch {
            // Keep the fallback detail if the response is not JSON.
          }
          throw new Error(detail);
        }

        const payload = await response.json();
        token.backendToken = payload.access_token;
        token.userId = payload.user.id;
        token.role = payload.user.role;
        token.status = payload.user.status;
        token.discordId = payload.user.discord_id;
      }

      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = String(token.userId ?? "");
        session.user.role = (token.role as "learner" | "admin" | "super_admin") ?? "learner";
        session.user.status = (token.status as "active" | "deactivated") ?? "active";
        session.user.discordId = String(token.discordId ?? "");
      }
      session.backendToken =
        typeof token.backendToken === "string" ? token.backendToken : undefined;
      return session;
    },
  },
});
