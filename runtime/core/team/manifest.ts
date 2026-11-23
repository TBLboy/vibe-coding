import { createHash } from "node:crypto";
import { validateServerPath } from "./layout.ts";

export interface ManifestEntry {
  version: number;
  hash: string;
}

export interface Manifest {
  schemaVersion: 1;
  cursor: number;
  entries: Record<string, ManifestEntry>;
}

const HASH_PATTERN = /^[0-9a-f]{64}$/u;

export function hashContent(bytes: Uint8Array | string): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function invalid(field: string): never {
  throw new Error(`manifest: invalid ${field}`);
}

function assertEntry(path: unknown, entry: unknown): asserts entry is ManifestEntry {
  if (typeof path !== "string" || !validateServerPath(path).ok) invalid("path");
  if (typeof entry !== "object" || entry === null || Array.isArray(entry)) invalid("entry");
  const candidate = entry as Record<string, unknown>;
  if (typeof candidate.version !== "number" || !Number.isSafeInteger(candidate.version) || candidate.version < 1) {
    invalid("version");
  }
  if (typeof candidate.hash !== "string" || !HASH_PATTERN.test(candidate.hash)) invalid("hash");
}

function assertManifest(value: unknown): asserts value is Manifest {
  if (typeof value !== "object" || value === null || Array.isArray(value)) invalid("object");
  const candidate = value as Record<string, unknown>;
  if (candidate.schemaVersion !== 1) invalid("schemaVersion");
  if (!Number.isSafeInteger(candidate.cursor) || (candidate.cursor as number) < 0) invalid("cursor");
  if (typeof candidate.entries !== "object" || candidate.entries === null || Array.isArray(candidate.entries)) {
    invalid("entries");
  }
  for (const [path, entry] of Object.entries(candidate.entries as Record<string, unknown>)) {
    assertEntry(path, entry);
  }
}

function orderedManifest(manifest: Manifest): Manifest {
  assertManifest(manifest);
  const entries: Record<string, ManifestEntry> = {};
  for (const path of Object.keys(manifest.entries).sort()) {
    const entry = manifest.entries[path];
    entries[path] = { version: entry.version, hash: entry.hash };
  }
  return { schemaVersion: 1, cursor: manifest.cursor, entries };
}

export function parseManifest(text: string): Manifest {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new Error("manifest: invalid json");
  }
  assertManifest(value);
  return orderedManifest(value);
}

export function serializeManifest(manifest: Manifest): string {
  return `${JSON.stringify(orderedManifest(manifest), null, 2)}\n`;
}

export type LocalClassification = "unchanged" | "modified" | "missing" | "new";

export function classifyLocal(
  entry: ManifestEntry | undefined,
  localHash: string | null,
): LocalClassification {
  if (entry === undefined) {
    if (localHash === null) throw new Error("classifyLocal requires an entry or a local hash");
    return "new";
  }
  if (localHash === null) return "missing";
  return localHash === entry.hash ? "unchanged" : "modified";
}

export function setEntry(manifest: Manifest, path: string, entry: ManifestEntry): Manifest {
  assertManifest(manifest);
  assertEntry(path, entry);
  return {
    schemaVersion: 1,
    cursor: manifest.cursor,
    entries: { ...manifest.entries, [path]: { ...entry } },
  };
}

export function removeEntry(manifest: Manifest, path: string): Manifest {
  assertManifest(manifest);
  if (!validateServerPath(path).ok) invalid("path");
  const entries = { ...manifest.entries };
  delete entries[path];
  return { schemaVersion: 1, cursor: manifest.cursor, entries };
}
