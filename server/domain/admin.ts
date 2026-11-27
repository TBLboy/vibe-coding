import { timingSafeEqual } from "node:crypto";
import { hashToken } from "./secrets.ts";

export const MIN_ADMIN_TOKEN_LENGTH = 32;

/** Startup check: refuse to run without a strong static admin credential. */
export function readAdminToken(env: NodeJS.ProcessEnv = process.env): string {
  const token = env.WORKBENCH_ADMIN_TOKEN;
  if (typeof token !== "string" || token.length < MIN_ADMIN_TOKEN_LENGTH) {
    throw new Error(`WORKBENCH_ADMIN_TOKEN must be set to at least ${MIN_ADMIN_TOKEN_LENGTH} characters`);
  }
  return token;
}

/** Constant-time comparison; hashing first equalises lengths. */
export function isAdmin(expected: string, presented: string): boolean {
  return timingSafeEqual(Buffer.from(hashToken(expected)), Buffer.from(hashToken(presented)));
}
