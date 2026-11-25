import { validateServerPath } from "./layout.ts";

export interface Change {
  seq: number;
  path: string;
  op: "upsert" | "delete";
  version: number;
  hash?: string;
}

const HASH_PATTERN = /^[0-9a-f]{64}$/u;

function assertNonNegativeInteger(value: unknown, field: string): asserts value is number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new Error(`change-feed: invalid ${field}`);
  }
}

function assertPositiveInteger(value: unknown, field: string): asserts value is number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1) {
    throw new Error(`change-feed: invalid ${field}`);
  }
}

export function validateChanges(since: number, changes: Change[]): void {
  assertNonNegativeInteger(since, "since");
  if (!Array.isArray(changes)) throw new Error("change-feed: invalid changes");

  let expected = since + 1;
  for (const change of changes) {
    if (typeof change !== "object" || change === null) throw new Error("change-feed: invalid change");
    assertPositiveInteger(change.seq, "seq");
    if (change.seq !== expected) throw new Error("change-feed: sequence is not contiguous");
    expected += 1;

    if (typeof change.path !== "string" || !validateServerPath(change.path).ok) {
      throw new Error("change-feed: invalid path");
    }
    if (change.op !== "upsert" && change.op !== "delete") {
      throw new Error("change-feed: invalid op");
    }
    assertPositiveInteger(change.version, "version");
    if (change.op === "upsert" && (typeof change.hash !== "string" || !HASH_PATTERN.test(change.hash))) {
      throw new Error("change-feed: invalid hash");
    }
    if (change.hash !== undefined && (typeof change.hash !== "string" || !HASH_PATTERN.test(change.hash))) {
      throw new Error("change-feed: invalid hash");
    }
  }
}

export function advanceCursor(current: number, changes: Change[]): number {
  validateChanges(current, changes);
  return changes.length === 0 ? current : changes[changes.length - 1].seq;
}
