import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

// Both branches carry this directory byte for byte. Hashing ignores the platform line ending.
const dir = import.meta.dirname;
const SELF = "contracts-sync.test.ts";
const digest = (name: string) =>
  createHash("sha256").update(readFileSync(resolve(dir, name), "utf8").replace(/\r\n/g, "\n")).digest("hex");

function listed(): Map<string, string> {
  const entries = new Map<string, string>();
  for (const line of readFileSync(resolve(dir, "SHA256SUMS"), "utf8").replace(/\r\n/g, "\n").split("\n")) {
    if (line.trim() === "") continue;
    const match = /^([0-9a-f]{64}) {2}([A-Za-z0-9._-]+)$/u.exec(line);
    assert.ok(match, `malformed SHA256SUMS line: ${line}`);
    entries.set(match[2], match[1]);
  }
  return entries;
}

test("shared contract files match the committed SHA-256 list", () => {
  const entries = listed();
  assert.ok(entries.size > 0, "SHA256SUMS is empty");
  for (const [name, expected] of entries) {
    assert.equal(digest(name), expected, `${name} differs from the committed shared contract`);
  }
});

test("every TypeScript file in the contract directory is listed", () => {
  const entries = listed();
  const present = readdirSync(dir).filter((name) => name.endsWith(".ts") && name !== SELF);
  assert.deepEqual([...present].sort(), [...entries.keys()].sort());
});
