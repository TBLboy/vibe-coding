import { Buffer } from "node:buffer";

export type ValidPath = { ok: true; path: string };
export type InvalidPath = { ok: false; reason: string };
export type PathValidation = ValidPath | InvalidPath;

const MAX_PATH_BYTES = 1024;
const MAX_SEGMENT_BYTES = 255;
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/u;

/** Validate a server-side path without normalizing it. */
export function validateServerPath(path: unknown): PathValidation {
  if (typeof path !== "string") return { ok: false, reason: "path must be a string" };
  if (path.length === 0) return { ok: false, reason: "path is empty" };
  if (path.startsWith("/")) return { ok: false, reason: "path must not be absolute" };
  if (path.includes("\\")) return { ok: false, reason: "path must not contain backslash" };
  if (CONTROL_CHARACTERS.test(path)) return { ok: false, reason: "path contains control character" };
  if (Buffer.byteLength(path, "utf8") > MAX_PATH_BYTES) {
    return { ok: false, reason: "path is too long" };
  }

  const segments = path.split("/");
  for (const segment of segments) {
    if (segment.length === 0) return { ok: false, reason: "path contains empty segment" };
    if (segment === "." || segment === "..") {
      return { ok: false, reason: "path contains dot segment" };
    }
    if (Buffer.byteLength(segment, "utf8") > MAX_SEGMENT_BYTES) {
      return { ok: false, reason: "path segment is too long" };
    }
  }

  return { ok: true, path };
}

/** Synced paths: AGENTS.md or anything under .vibe/, except the device-private .vibe/.sync/. */
export function validateSyncPath(path: unknown): PathValidation {
  const base = validateServerPath(path);
  if (!base.ok) return base;
  const p = base.path;
  if (p === "AGENTS.md") return base;
  if (!p.startsWith(".vibe/")) return { ok: false, reason: "path must be AGENTS.md or under .vibe/" };
  if (p.toLowerCase() === ".vibe/.sync" || p.toLowerCase().startsWith(".vibe/.sync/")) return { ok: false, reason: "path is device-private" };
  for (const segment of p.split('/')) {
    if (/[<>:"|?*]/u.test(segment) || /[. ]$/u.test(segment) || /^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\.|$)/iu.test(segment) || /[\uD800-\uDFFF]/u.test(segment)) return { ok: false, reason: 'unsafe cross-platform segment' };
  }
  return base;
}
