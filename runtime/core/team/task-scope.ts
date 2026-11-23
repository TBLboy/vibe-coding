import { Buffer } from "node:buffer";
import { validateServerPath } from "./layout.ts";

export interface ScopeOverlap {
  left: string;
  right: string;
  reason: "same-path" | "directory-prefix";
}

/** Relative literals only: a final slash means directory prefix, not glob syntax. */
export function normalizeScope(paths: readonly string[]): string[] {
  if (!Array.isArray(paths)) {
    throw new Error("scope must be an array of paths");
  }
  if (paths.length > 200) throw new Error("scope exceeds 200 entries");
  for (const path of paths) {
    if (typeof path !== "string") throw new Error("scope must be an array of paths");
  }
  const normalized = paths.map(path => {
    let value = path.trim().replaceAll("\\", "/").replace(/\/+/gu, "/");
    while (value.startsWith("./")) value = value.slice(2);
    if (value.startsWith("/") || /^[A-Za-z]:/u.test(value)) throw new Error("scope path must be relative");
    if (Buffer.byteLength(value, "utf8") > 1024) throw new Error("scope path is too long");
    const base = value.endsWith("/") ? value.slice(0, -1) : value;
    const valid = validateServerPath(base);
    if (!valid.ok) throw new Error(`invalid scope path: ${valid.reason}`);
    return value;
  });
  return [...new Set(normalized)].sort();
}

export function findScopeOverlaps(left: readonly string[], right: readonly string[]): ScopeOverlap[] {
  const leftPaths = normalizeScope(left), rightPaths = normalizeScope(right);
  const overlaps: ScopeOverlap[] = [];
  for (const a of leftPaths) {
    for (const b of rightPaths) {
      if (a === b) overlaps.push({ left: a, right: b, reason: "same-path" });
      else if ((a.endsWith("/") && b.startsWith(a)) || (b.endsWith("/") && a.startsWith(b))) {
        overlaps.push({ left: a, right: b, reason: "directory-prefix" });
      }
    }
  }
  return overlaps;
}
