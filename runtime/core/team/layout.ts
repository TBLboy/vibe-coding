import { Buffer } from "node:buffer";

export const MEMORY_LAYERS = ["constitution", "specs", "work", "members", "activity"] as const;
export type Layer = typeof MEMORY_LAYERS[number] | "index";

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

export function layerOf(path: string): Layer | undefined {
  if (path === "index.json") return "index";
  for (const layer of MEMORY_LAYERS) {
    if (path.startsWith(`${layer}/`)) return layer;
  }
  return undefined;
}
