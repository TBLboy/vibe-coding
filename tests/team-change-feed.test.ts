import assert from "node:assert/strict";
import test from "node:test";
import {
  advanceCursor,
  validateChanges,
  type Change,
} from "../runtime/core/team/change-feed.ts";

const HASH = "a".repeat(64);

function upsert(seq: number): Change {
  return { seq, path: "specs/a.md", op: "upsert", version: seq, hash: HASH };
}

test("change-feed accepts a contiguous batch and advances its cursor", () => {
  const changes = [upsert(4), upsert(5)];
  validateChanges(3, changes);
  assert.equal(advanceCursor(3, changes), 5);
  assert.equal(advanceCursor(5, []), 5);
});

test("change-feed rejects sequence gaps and out-of-order batches", () => {
  assert.throws(() => validateChanges(3, [upsert(5)]), /seq|contiguous/);
  assert.throws(() => validateChanges(3, [upsert(4), upsert(6)]), /seq|contiguous/);
  assert.throws(() => validateChanges(3, [{ ...upsert(4), seq: 0 }]), /seq/);
});

test("change-feed validates paths, versions, operations and hashes", () => {
  assert.throws(() => validateChanges(0, [{ ...upsert(1), path: "../escape" }]), /path/);
  assert.throws(() => validateChanges(0, [{ ...upsert(1), version: 0 }]), /version/);
  assert.throws(() => validateChanges(0, [{ ...upsert(1), op: "other" as "upsert" }]), /op/);
  assert.throws(() => validateChanges(0, [{ ...upsert(1), hash: "bad" }]), /hash/);
  assert.throws(
    () => validateChanges(0, [{ seq: 1, path: "specs/a.md", op: "upsert", version: 1 }]),
    /hash/,
  );
});

test("delete changes do not require content hashes", () => {
  const change: Change = { seq: 1, path: "specs/a.md", op: "delete", version: 2 };
  validateChanges(0, [change]);
});

test("change-feed rejects invalid cursors and unsafe integer counters", () => {
  for (const since of [-1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => validateChanges(since, []), /since/);
  }
  for (const value of [0, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => validateChanges(0, [{ ...upsert(1), version: value }]), /version/);
  }
  assert.throws(() => advanceCursor(2, [upsert(2)]), /contiguous/);
});
