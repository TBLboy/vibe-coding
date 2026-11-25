import assert from "node:assert/strict";
import test from "node:test";
import {
  classifyLocal,
  hashContent,
  parseManifest,
  removeEntry,
  serializeManifest,
  setEntry,
  type Manifest,
} from "./manifest.ts";

const HASH_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

test("manifest round-trip preserves prototype-like names as ordinary own keys",()=>{
  const entries=Object.fromEntries(["__proto__","constructor"].map(path=>[path,{version:1,hash:HASH_ABC}]));
  const parsed=parseManifest(serializeManifest({schemaVersion:1,cursor:2,entries}));
  assert.equal(Object.hasOwn(parsed.entries,"__proto__"),true);assert.equal(Object.hasOwn(parsed.entries,"constructor"),true);
  assert.deepEqual(Object.keys(parsed.entries),["__proto__","constructor"]);
});

function sampleManifest(): Manifest {
  return {
    schemaVersion: 1,
    cursor: 7,
    entries: {
      "specs/b.md": { version: 2, hash: HASH_ABC },
      "specs/a.md": { version: 1, hash: HASH_ABC },
    },
  };
}

test("hashContent matches the known sha256 of 'abc'", () => {
  assert.equal(hashContent("abc"), HASH_ABC);
  assert.equal(hashContent(new TextEncoder().encode("abc")), HASH_ABC);
  assert.notEqual(hashContent("abd"), HASH_ABC);
});

test("manifest serialization is stable and round-trips", () => {
  const manifest = sampleManifest();
  const text = serializeManifest(manifest);
  assert.ok(text.indexOf("specs/a.md") < text.indexOf("specs/b.md"), "entries must be sorted");
  assert.equal(serializeManifest(parseManifest(text)), text);
  assert.deepEqual(parseManifest(text), manifest);
});

test("parseManifest rejects malformed documents", () => {
  assert.throws(() => parseManifest("not json"), /manifest: invalid json/);
  assert.throws(
    () => parseManifest(JSON.stringify({ schemaVersion: 2, cursor: 0, entries: {} })),
    /schemaVersion/,
  );
  assert.throws(
    () => parseManifest(JSON.stringify({ schemaVersion: 1, cursor: -1, entries: {} })),
    /cursor/,
  );
  assert.throws(
    () =>
      parseManifest(
        JSON.stringify({ schemaVersion: 1, cursor: 0, entries: { "specs/a.md": { version: 0, hash: HASH_ABC } } }),
      ),
    /version/,
  );
  assert.throws(
    () =>
      parseManifest(
        JSON.stringify({ schemaVersion: 1, cursor: 0, entries: { "specs/a.md": { version: 1, hash: "ABC" } } }),
      ),
    /hash/,
  );
  assert.throws(
    () =>
      parseManifest(
        JSON.stringify({ schemaVersion: 1, cursor: 0, entries: { "../escape": { version: 1, hash: HASH_ABC } } }),
      ),
    /path/,
  );
});

test("classifyLocal distinguishes unchanged, modified, missing and new", () => {
  const entry = { version: 3, hash: HASH_ABC };
  assert.equal(classifyLocal(entry, HASH_ABC), "unchanged");
  assert.equal(classifyLocal(entry, hashContent("other")), "modified");
  assert.equal(classifyLocal(entry, null), "missing");
  assert.equal(classifyLocal(undefined, HASH_ABC), "new");
  assert.throws(() => classifyLocal(undefined, null), /entry or a local hash/);
});

test("setEntry and removeEntry return new immutable manifests", () => {
  const manifest = sampleManifest();
  const added = setEntry(manifest, "work/T-1.json", { version: 9, hash: HASH_ABC });
  assert.equal(manifest.entries["work/T-1.json"], undefined);
  assert.deepEqual(added.entries["work/T-1.json"], { version: 9, hash: HASH_ABC });

  const removed = removeEntry(added, "specs/a.md");
  assert.ok(removed.entries["specs/a.md"] === undefined);
  assert.ok(added.entries["specs/a.md"] !== undefined);
});
