import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    backendToken?: string;
    user: DefaultSession["user"] & {
      id: string;
      role: "learner" | "admin" | "super_admin";
      status: "active" | "deactivated";
      discordId: string;
    };
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    backendToken?: string;
    userId?: string;
    role?: "learner" | "admin" | "super_admin";
    status?: "active" | "deactivated";
    discordId?: string;
  }
}
