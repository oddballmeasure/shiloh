import path from "node:path";

export const AUTH_DIRECTORY = path.resolve(__dirname, ".auth");
export const LEARNER_STATE_PATH = path.join(AUTH_DIRECTORY, "learner.json");
export const ADMIN_STATE_PATH = path.join(AUTH_DIRECTORY, "admin.json");
