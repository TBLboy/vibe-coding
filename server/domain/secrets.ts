import { createHash, randomBytes } from "node:crypto";

export const issueSecret = (bytes = 32): string => randomBytes(bytes).toString("base64url");
export const hashToken = (secret: string): string => createHash("sha256").update(secret).digest("hex");
